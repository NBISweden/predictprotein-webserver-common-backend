import os
import sys
import tempfile
import re
import subprocess
from datetime import datetime
from dateutil import parser as dtparser
from pytz import timezone
import time
import math
import shutil
import json
import logging

# for dealing with IP address and country names
from geoip import geolite2
import pycountry

#import models for spyne
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.views.decorators.csrf import csrf_exempt  
from spyne.error import ResourceNotFoundError, ResourceAlreadyExistsError
from spyne.server.django import DjangoApplication
from spyne.model.primitive import Unicode, Integer
from spyne.model.complex import Iterable
from spyne.service import ServiceBase
from spyne.protocol.soap import Soap11
from spyne.application import Application
from spyne.decorator import rpc
from spyne.util.django import DjangoComplexModel, DjangoServiceBase
from spyne.server.wsgi import WsgiApplication

# for user authentication
from django.contrib.auth import authenticate, login, logout

# import variables from settings
from django.conf import settings

SITE_ROOT = os.path.dirname(os.path.realpath(__file__))
progname =  os.path.basename(__file__)
rootname_progname = os.path.splitext(progname)[0]
path_app = "%s/app"%(SITE_ROOT)
sys.path.append(path_app)
path_log = "%s/static/log"%(SITE_ROOT)
path_stat = "%s/stat"%(path_log)
path_result = "%s/static/result"%(SITE_ROOT)
path_tmp = "%s/static/tmp"%(SITE_ROOT)
path_md5 = "%s/static/md5"%(SITE_ROOT)
python_exec = os.path.realpath("%s/../../env/bin/python"%(SITE_ROOT))

import myfunc
import webserver_common as webcom

TZ = webcom.TZ
os.environ['TZ'] = TZ
time.tzset()

g_params = {}

# global parameters
g_params['BASEURL'] = "/pred/";
g_params['MAXSIZE_UPLOAD_FILE_IN_MB'] = 10
g_params['MIN_LEN_SEQ'] = 10      # minimum length of the query sequence
g_params['MAX_LEN_SEQ'] = 10000   # maximum length of the query sequence
g_params['MAX_DAYS_TO_SHOW'] = 30
g_params['BIG_NUMBER'] = 100000
g_params['MAX_NUMSEQ_FOR_FORCE_RUN'] = 100
g_params['MAX_NUMSEQ_PER_JOB'] = 100
g_params['AVERAGE_RUNTIME_PER_SEQ_IN_SEC'] = 120
g_params['MAX_ROWS_TO_SHOW_IN_TABLE'] = 2000
g_params['MAXSIZE_UPLOAD_FILE_IN_BYTE'] = g_params['MAXSIZE_UPLOAD_FILE_IN_MB'] * 1024*1024
g_params['FORMAT_DATETIME'] = webcom.FORMAT_DATETIME


suq_basedir = "/tmp"
# if os.path.exists("/scratch"):
#     suq_basedir = "/scratch"
# elif os.path.exists("/tmp"):
#     suq_basedir = "/tmp"
rundir = SITE_ROOT
suq_exec = "/usr/bin/suq";

qd_fe_scriptfile = "%s/qd_fe.py"%(path_app)
gen_errfile = "%s/static/log/%s.err"%(SITE_ROOT, progname)

# Create your views here.
from django.shortcuts import render
from django.http import HttpResponse
from django.http import HttpRequest
from django.http import HttpResponseRedirect
from django.views.static import serve


#from pred.models import Query
from proj.pred.models import SubmissionForm
from proj.pred.models import FieldContainer
from django.template import Context, loader

def set_basic_config(request, info):# {{{
    """Set basic configurations for the template dict"""
    username = request.user.username
    client_ip = request.META['REMOTE_ADDR']
    if username in settings.SUPER_USER_LIST:
        isSuperUser = True
        divided_logfile_query =  "%s/%s/%s"%(SITE_ROOT,
                "static/log", "submitted_seq.log")
        divided_logfile_finished_jobid =  "%s/%s/%s"%(SITE_ROOT,
                "static/log", "failed_job.log")
    else:
        isSuperUser = False
        divided_logfile_query =  "%s/%s/%s"%(SITE_ROOT,
                "static/log/divided", "%s_submitted_seq.log"%(client_ip))
        divided_logfile_finished_jobid =  "%s/%s/%s"%(SITE_ROOT,
                "static/log/divided", "%s_failed_job.log"%(client_ip))

    if isSuperUser:
        info['MAX_DAYS_TO_SHOW'] = g_params['BIG_NUMBER']
    else:
        info['MAX_DAYS_TO_SHOW'] = g_params['MAX_DAYS_TO_SHOW']


    info['username'] = username
    info['isSuperUser'] = isSuperUser
    info['divided_logfile_query'] = divided_logfile_query
    info['divided_logfile_finished_jobid'] = divided_logfile_finished_jobid
    info['client_ip'] = client_ip
    info['BASEURL'] = g_params['BASEURL']
    info['STATIC_URL'] = settings.STATIC_URL
# }}}
def SetColorStatus(status):#{{{
    if status == "Finished":
        return "green"
    elif status == "Failed":
        return "red"
    elif status == "Running":
        return "blue"
    else:
        return "black"
#}}}

def index(request):#{{{
    logger = logging.getLogger(__name__)
    if not os.path.exists(path_result):
        os.mkdir(path_result, 0755)
    if not os.path.exists(path_result):
        os.mkdir(path_tmp, 0755)
    if not os.path.exists(path_md5):
        os.mkdir(path_md5, 0755)

    url_scheme = "http://"
    if request.is_secure():
        url_scheme = "https://"

    base_www_url_file = "%s/static/log/base_www_url.txt"%(SITE_ROOT)
    if not os.path.exists(base_www_url_file):
        base_www_url = url_scheme + request.META['HTTP_HOST']
        myfunc.WriteFile(base_www_url, base_www_url_file, "w", True)

    configfile = "%s/config/config.json"%(SITE_ROOT)
    config = {}
    if os.path.exists(configfile):
        text = myfunc.ReadFile(configfile)
        config = json.loads(text)

    if rootname_progname in config:
        g_params.update(config[rootname_progname])
        g_params['MAXSIZE_UPLOAD_FILE_IN_BYTE'] = g_params['MAXSIZE_UPLOAD_FILE_IN_MB'] * 1024*1024
    logger.info("index visited")
    return submit_seq(request)
#}}}
def login(request):#{{{
    #logout(request)
    info = {}
    set_basic_config(request, info)
    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/login.html', info)
#}}}
def submit_seq(request):#{{{
    info = {}
    set_basic_config(request, info)

    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = SubmissionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # redirect to a new URL:

            jobname = request.POST['jobname']
            email = request.POST['email']
            rawseq = request.POST['rawseq'] + "\n" # force add a new line
            isForceRun = False
            isKeepTempFile = False

            for tup in form.second_method_choices:
                if tup[0] == second_method:
                    second_method = tup[1]
                    break

            if 'pfamscan_clanoverlap' in request.POST:
                pfamscan_clanoverlap = True
            if 'forcerun' in request.POST:
                isForceRun = True
            if 'keeptmpfile' in request.POST:
                isKeepTempFile = True

            try:
                seqfile = request.FILES['seqfile']
            except KeyError, MultiValueDictKeyError:
                seqfile = ""
            date_str = time.strftime(g_params['FORMAT_DATETIME'])
            query = {}
            query['rawseq'] = rawseq
            query['seqfile'] = seqfile
            query['email'] = email
            query['jobname'] = jobname
            query['date'] = date_str
            query['client_ip'] = info['client_ip']
            query['errinfo'] = ""
            query['method_submission'] = "web"
            query['isForceRun'] = isForceRun
            query['isKeepTempFile'] = isKeepTempFile
            query['username'] = username

            is_valid_parameter = True
            if 'name_software' in query_para and query_para['name_software'] in ['prodres', 'docker_prodres']:
                is_valid_parameter = webcom.ValidateParameter_PRODRES(query)

            is_valid_query = False
            if is_valid_parameter:
                is_valid_query = webcom.ValidateQuery(request, query, g_params)


            if is_valid_parameter and is_valid_query:
                jobid = RunQuery(request, query)

                # type of method_submission can be web or wsdl
                #date, jobid, IP, numseq, size, jobname, email, method_submission
                log_record = "%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\n"%(query['date'], jobid,
                        query['client_ip'], query['numseq'],
                        len(query['rawseq']),query['jobname'], query['email'],
                        query['method_submission'])
                main_logfile_query = "%s/%s/%s"%(SITE_ROOT, "static/log", "submitted_seq.log")
                myfunc.WriteFile(log_record, main_logfile_query, "a")

                divided_logfile_query =  "%s/%s/%s"%(SITE_ROOT,
                        "static/log/divided", "%s_submitted_seq.log"%(query['client_ip']))
                divided_logfile_finished_jobid =  "%s/%s/%s"%(SITE_ROOT,
                        "static/log/divided", "%s_finished_job.log"%(query['client_ip']))
                if query['client_ip'] != "":
                    myfunc.WriteFile(log_record, divided_logfile_query, "a")


                file_seq_warning = "%s/%s/%s/%s"%(SITE_ROOT, "static/result", jobid, "query.warn.txt")
                query['file_seq_warning'] = os.path.basename(file_seq_warning)
                if query['warninfo'] != "":
                    myfunc.WriteFile(query['warninfo'], file_seq_warning, "a")

                query['jobid'] = jobid
                query['raw_query_seqfile'] = "query.raw.fa"
                query['BASEURL'] = g_params['BASEURL']

                # start the qd_fe if not, in the background
#                 cmd = [qd_fe_scriptfile]

                base_www_url = url_scheme + request.META['HTTP_HOST']
                if webcom.IsFrontEndNode(base_www_url): #run the daemon only at the frontend
                    cmd = "nohup %s %s &"%(python_exec, qd_fe_scriptfile)
                    os.system(cmd)

                if query['numseq'] < 0: #go to result page anyway
                    query['jobcounter'] = webcom.GetJobCounter(info)
                    return render(request, 'pred/thanks.html', query)
                else:
                    return get_results(request, jobid)

            else:
                query['jobcounter'] = webcom.GetJobCounter(info)
                return render(request, 'pred/badquery.html', query)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = SubmissionForm()

    jobcounter = webcom.GetJobCounter(info)
    info['form'] = form
    info['jobcounter'] = jobcounter
    return render(request, 'pred/submit_seq.html', info)
#}}}

def RunQuery(request, query):#{{{
    url_scheme = "http://"
    if request.is_secure():
        url_scheme = "https://"
    errmsg = []
    tmpdir = tempfile.mkdtemp(prefix="%s/static/tmp/tmp_"%(SITE_ROOT))
    rstdir = tempfile.mkdtemp(prefix="%s/static/result/rst_"%(SITE_ROOT))
    os.chmod(tmpdir, 0755)
    os.chmod(rstdir, 0755)
    jobid = os.path.basename(rstdir)
    query['jobid'] = jobid

# write files for the query
    jobinfofile = "%s/jobinfo"%(rstdir)
    rawseqfile = "%s/query.raw.fa"%(rstdir)
    seqfile_t = "%s/query.fa"%(tmpdir)
    seqfile_r = "%s/query.fa"%(rstdir)
    warnfile = "%s/warn.txt"%(tmpdir)
    logfile = "%s/runjob.log"%(rstdir)

    query_para = {}
    for item in ['pfamscan_bitscore', 'pfamscan_evalue','pfamscan_clanoverlap','jackhmmer_threshold_type', 'jackhmmer_evalue','jackhmmer_bitscore', 'jackhmmer_iteration', 'psiblast_evalue', 'psiblast_iteration', 'psiblast_outfmt', 'second_method', 'isKeepTempFile']:
        if item in query:
            query_para[item] = query[item]

    query_parafile = "%s/query.para.txt"%(rstdir)

    myfunc.WriteFile("tmpdir = %s\n"%(tmpdir), logfile, "a")

    jobinfo_str = "%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\n"%(query['date'], jobid,
            query['client_ip'], query['numseq'],
            len(query['rawseq']),query['jobname'], query['email'],
            query['method_submission'])
    errmsg.append(myfunc.WriteFile(jobinfo_str, jobinfofile, "w"))
    errmsg.append(myfunc.WriteFile(query['rawseq'], rawseqfile, "w"))
    errmsg.append(myfunc.WriteFile(query['filtered_seq'], seqfile_t, "w"))
    errmsg.append(myfunc.WriteFile(query['filtered_seq'], seqfile_r, "w"))

    errmsg.append(myfunc.WriteFile(json.dumps(query_para, sort_keys=True), query_parafile, "w"))

    base_www_url = url_scheme + request.META['HTTP_HOST']
    query['base_www_url'] = base_www_url


    # for single sequence job submitted via web interface, submit to local
    # queue
    if query['numseq'] <= 1: #single sequence jobs submitted via web interface queued in the front-end server
        query['numseq_this_user'] = 1
        SubmitQueryToLocalQueue(query, tmpdir, rstdir, isOnlyGetCache=False)
    else: #all other jobs are submitted to the frontend with isOnlyGetCache=True
        query['numseq_this_user'] = 1
        SubmitQueryToLocalQueue(query, tmpdir, rstdir, isOnlyGetCache=True)


    forceruntagfile = "%s/forcerun"%(rstdir)
    if query['isForceRun']:
        myfunc.WriteFile("", forceruntagfile)
    return jobid
#}}}
def RunQuery_wsdl_local(rawseq, filtered_seq, seqinfo):#{{{
# submit the wsdl job to the local queue
    errmsg = []
    tmpdir = tempfile.mkdtemp(prefix="%s/static/tmp/tmp_"%(SITE_ROOT))
    rstdir = tempfile.mkdtemp(prefix="%s/static/result/rst_"%(SITE_ROOT))
    os.chmod(tmpdir, 0755)
    os.chmod(rstdir, 0755)
    jobid = os.path.basename(rstdir)
    seqinfo['jobid'] = jobid
    numseq = seqinfo['numseq']
    para_str = seqinfo['para_str']

# write files for the query
    jobinfofile = "%s/jobinfo"%(rstdir)
    rawseqfile = "%s/query.raw.fa"%(rstdir)
    seqfile_t = "%s/query.fa"%(tmpdir)
    seqfile_r = "%s/query.fa"%(rstdir)
    query_parafile = "%s/query.para.txt"%(rstdir)
    warnfile = "%s/warn.txt"%(tmpdir)
    jobinfo_str = "%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\n"%(seqinfo['date'], jobid,
            seqinfo['client_ip'], seqinfo['numseq'],
            len(rawseq),seqinfo['jobname'], seqinfo['email'],
            seqinfo['method_submission'])
    errmsg.append(myfunc.WriteFile(jobinfo_str, jobinfofile, "w"))
    errmsg.append(myfunc.WriteFile(rawseq, rawseqfile, "w"))
    errmsg.append(myfunc.WriteFile(para_str, query_parafile, "w"))
    errmsg.append(myfunc.WriteFile(filtered_seq, seqfile_t, "w"))
    errmsg.append(myfunc.WriteFile(filtered_seq, seqfile_r, "w"))
    base_www_url = seqinfo['url_scheme'] + seqinfo['hostname']
    seqinfo['base_www_url'] = base_www_url

    rtvalue = SubmitQueryToLocalQueue(seqinfo, tmpdir, rstdir, isOnlyGetCache=False)
    if rtvalue != 0:
        return "None"
    else:
        return jobid
#}}}
def SubmitQueryToLocalQueue(query, tmpdir, rstdir, isOnlyGetCache=False):#{{{
    scriptfile = "%s/app/submit_job_to_queue.py"%(SITE_ROOT)
    rstdir = "%s/%s"%(path_result, query['jobid'])
    runjob_errfile = "%s/runjob.err"%(rstdir)
    debugfile = "%s/debug.log"%(rstdir) #this log only for debugging
    runjob_logfile = "%s/runjob.log"%(rstdir)
    failedtagfile = "%s/%s"%(rstdir, "runjob.failed")
    rmsg = ""

    cmd = [python_exec, scriptfile, "-nseq", "%d"%query['numseq'], "-nseq-this-user",
            "%d"%query['numseq_this_user'], "-jobid", query['jobid'],
            "-outpath", rstdir, "-datapath", tmpdir, "-baseurl",
            query['base_www_url'] ]
    if query['email'] != "":
        cmd += ["-email", query['email']]
    if query['client_ip'] != "":
        cmd += ["-host", query['client_ip']]
    if query['isForceRun']:
        cmd += ["-force"]
    if isOnlyGetCache:
        cmd += ["-only-get-cache"]

    (isSuccess, t_runtime) = webcom.RunCmd(cmd, runjob_logfile, runjob_errfile)
    if not isSuccess:
        webcom.WriteDateTimeTagFile(failedtagfile, runjob_logfile, runjob_errfile)
        return 1
    else:
        return 0
#}}}

def thanks(request):#{{{
    #print "request.POST at thanks:", request.POST
    return HttpResponse("Thanks")
#}}}

def get_queue(request):#{{{
    errfile = "%s/server.err"%(path_result)
    info = {}
    set_basic_config(request, info)

    status = "Queued"
    info['header'] = ["No.", "JobID","JobName", "NumSeq", "Email",
            "QueueTime", "RunTime", "Date", "Source"]
    if info['isSuperUser']:
        info['header'].insert(5, "Host")

    hdl = myfunc.ReadLineByBlock(info['divided_logfile_query'])
    if hdl.failure:
        info['errmsg'] = ""
        pass
    else:
        finished_jobid_list = []
        if os.path.exists(info['divided_logfile_finished_jobid']):
            finished_jobid_list = myfunc.ReadIDList2(info['divided_logfile_finished_jobid'], 0, None)
        finished_jobid_set = set(finished_jobid_list)
        jobRecordList = []
        lines = hdl.readlines()
        current_time = datetime.now(timezone(TZ))
        while lines != None:
            for line in lines:
                strs = line.split("\t")
                if len(strs) < 7:
                    continue
                ip = strs[2]
                if not info['isSuperUser'] and ip != info['client_ip']:
                    continue
                jobid = strs[1]
                if jobid in finished_jobid_set:
                    continue

                rstdir = "%s/%s"%(path_result, jobid)
                starttagfile = "%s/%s"%(rstdir, "runjob.start")
                failedtagfile = "%s/%s"%(rstdir, "runjob.failed")
                finishtagfile = "%s/%s"%(rstdir, "runjob.finish")
                if (os.path.exists(rstdir) and 
                        not os.path.exists(starttagfile) and
                        not os.path.exists(failedtagfile) and
                        not os.path.exists(finishtagfile)):
                    jobRecordList.append(jobid)
            lines = hdl.readlines()
        hdl.close()

        jobinfo_list = []
        rank = 0
        for jobid in jobRecordList:
            rank += 1
            ip =  ""
            jobname = ""
            email = ""
            method_submission = "web"
            numseq = 1
            rstdir = "%s/%s"%(path_result, jobid)

            submit_date_str = ""
            finish_date_str = ""
            start_date_str = ""

            jobinfofile = "%s/jobinfo"%(rstdir)
            jobinfo = myfunc.ReadFile(jobinfofile).strip()
            jobinfolist = jobinfo.split("\t")
            if len(jobinfolist) >= 8:
                submit_date_str = jobinfolist[0]
                ip = jobinfolist[2]
                numseq = int(jobinfolist[3])
                jobname = jobinfolist[5]
                email = jobinfolist[6]
                method_submission = jobinfolist[7]

            starttagfile = "%s/runjob.start"%(rstdir)
            queuetime = ""
            runtime = ""
            isValidSubmitDate = True
            try:
                submit_date = webcom.datetime_str_to_time(submit_date_str)
            except ValueError:
                isValidSubmitDate = False

            if isValidSubmitDate:
                queuetime = myfunc.date_diff(submit_date, current_time)

            row_content = [rank, jobid, jobname[:20], numseq, email,
                    queuetime, runtime, submit_date_str, method_submission]
            if info['isSuperUser']:
                row_content.insert(5, ip)
            jobinfo_list.append(row_content)

        info['content'] = jobinfo_list

    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/queue.html', info)
#}}}
def get_running(request):#{{{
    # Get running jobs
    errfile = "%s/server.err"%(path_result)
    status = "Running"

    info = {}
    set_basic_config(request, info)
    info['header'] = ["No.", "JobID", "JobName", "NumSeq", "NumFinish", "Email",
            "QueueTime", "RunTime", "Date", "Source"]
    if info['isSuperUser']:
        info['header'].insert(6, "Host")

    hdl = myfunc.ReadLineByBlock(info['divided_logfile_query'])
    if hdl.failure:
        info['errmsg'] = ""
        pass
    else:
        finished_jobid_list = []
        if os.path.exists(info['divided_logfile_finished_jobid']):
            finished_jobid_list = myfunc.ReadIDList2(info['divided_logfile_finished_jobid'], 0, None)
        finished_jobid_set = set(finished_jobid_list)
        jobRecordList = []
        lines = hdl.readlines()
        current_time = datetime.now(timezone(TZ))
        while lines != None:
            for line in lines:
                strs = line.split("\t")
                if len(strs) < 7:
                    continue
                ip = strs[2]
                if not info['isSuperUser'] and ip != info['client_ip']:
                    continue
                jobid = strs[1]
                if jobid in finished_jobid_set:
                    continue
                rstdir = "%s/%s"%(path_result, jobid)
                starttagfile = "%s/%s"%(rstdir, "runjob.start")
                finishtagfile = "%s/%s"%(rstdir, "runjob.finish")
                failedtagfile = "%s/%s"%(rstdir, "runjob.failed")
                if (os.path.exists(rstdir) and os.path.exists(starttagfile) and (not
                    os.path.exists(finishtagfile) and not
                    os.path.exists(failedtagfile))):
                    jobRecordList.append(jobid)
            lines = hdl.readlines()
        hdl.close()

        jobinfo_list = []
        rank = 0
        for jobid in jobRecordList:
            rank += 1
            ip =  ""
            jobname = ""
            email = ""
            method_submission = "web"
            numseq = 1
            rstdir = "%s/%s"%(path_result, jobid)

            submit_date_str = ""
            finish_date_str = ""
            start_date_str = ""


            jobinfofile = "%s/jobinfo"%(rstdir)
            jobinfo = myfunc.ReadFile(jobinfofile).strip()
            jobinfolist = jobinfo.split("\t")
            if len(jobinfolist) >= 8:
                submit_date_str = jobinfolist[0]
                ip = jobinfolist[2]
                numseq = int(jobinfolist[3])
                jobname = jobinfolist[5]
                email = jobinfolist[6]
                method_submission = jobinfolist[7]

            finished_idx_file = "%s/finished_seqindex.txt"%(rstdir)
            numFinishedSeq = 0
            if os.path.exists(finished_idx_file):
                finished_idxlist = myfunc.ReadIDList(finished_idx_file)
                numFinishedSeq = len(set(finished_idxlist))

            starttagfile = "%s/runjob.start"%(rstdir)
            queuetime = ""
            runtime = ""
            isValidSubmitDate = True
            isValidStartDate = True
            try:
                submit_date = webcom.datetime_str_to_time(submit_date_str)
            except ValueError:
                isValidSubmitDate = False
            start_date_str = ""
            if os.path.exists(start_date_str):
                start_date_str = myfunc.ReadFile(starttagfile).strip()
            try:
                start_date = webcom.datetime_str_to_time(start_date_str)
            except ValueError:
                isValidStartDate = False
            if isValidStartDate:
                runtime = myfunc.date_diff(start_date, current_time)
            if isValidStartDate and isValidSubmitDate:
                queuetime = myfunc.date_diff(submit_date, start_date)

            row_content = [rank, jobid, jobname[:20], numseq, numFinishedSeq,
                    email, queuetime, runtime, submit_date_str,
                    method_submission]
            if info['isSuperUser']:
                row_content.insert(6, ip)
            jobinfo_list.append(row_content)

        info['content'] = jobinfo_list

    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/running.html', info)
#}}}
def get_finished_job(request):#{{{
    info = {}
    set_basic_config(request, info)
    info['header'] = ["No.", "JobID","JobName", "NumSeq", "Email",
            "QueueTime","RunTime", "Date", "Source"]
    if info['isSuperUser']:
        info['header'].insert(5, "Host")

    hdl = myfunc.ReadLineByBlock(info['divided_logfile_query'])
    if hdl.failure:
        #info['errmsg'] = "Failed to retrieve finished job information!"
        info['errmsg'] = ""
        pass
    else:
        finished_job_dict = myfunc.ReadFinishedJobLog(info['divided_logfile_finished_jobid'])
        jobRecordList = []
        lines = hdl.readlines()
        current_time = datetime.now(timezone(TZ))
        while lines != None:
            for line in lines:
                strs = line.split("\t")
                if len(strs) < 7:
                    continue
                ip = strs[2]
                if not info['isSuperUser'] and ip != info['client_ip']:
                    continue

                submit_date_str = strs[0]
                isValidSubmitDate = True
                try:
                    submit_date = webcom.datetime_str_to_time(submit_date_str)
                except ValueError:
                    isValidSubmitDate = False
                if not isValidSubmitDate:
                    continue

                diff_date = current_time - submit_date
                if diff_date.days > info['MAX_DAYS_TO_SHOW']:
                    continue
                jobid = strs[1]
                rstdir = "%s/%s"%(path_result, jobid)
                if jobid in finished_job_dict:
                    status = finished_job_dict[jobid][0]
                    if status == "Finished":
                        jobRecordList.append(jobid)
                else:
                    finishtagfile = "%s/%s"%(rstdir, "runjob.finish")
                    failedtagfile = "%s/%s"%(rstdir, "runjob.failed")
                    if (os.path.exists(rstdir) and  os.path.exists(finishtagfile) and
                            not os.path.exists(failedtagfile)):
                        jobRecordList.append(jobid)
            lines = hdl.readlines()
        hdl.close()

        jobinfo_list = []
        rank = 0
        for jobid in jobRecordList:
            rank += 1
            ip =  ""
            jobname = ""
            email = ""
            method_submission = "web"
            numseq = 1
            rstdir = "%s/%s"%(path_result, jobid)
            starttagfile = "%s/runjob.start"%(rstdir)
            finishtagfile = "%s/runjob.finish"%(rstdir)

            submit_date_str = ""
            finish_date_str = ""
            start_date_str = ""

            if jobid in finished_job_dict:
                status = finished_job_dict[jobid][0]
                jobname = finished_job_dict[jobid][1]
                ip = finished_job_dict[jobid][2]
                email = finished_job_dict[jobid][3]
                numseq = finished_job_dict[jobid][4]
                method_submission = finished_job_dict[jobid][5]
                submit_date_str = finished_job_dict[jobid][6]
                start_date_str = finished_job_dict[jobid][7]
                finish_date_str = finished_job_dict[jobid][8]
            else:
                jobinfofile = "%s/jobinfo"%(rstdir)
                jobinfo = myfunc.ReadFile(jobinfofile).strip()
                jobinfolist = jobinfo.split("\t")
                if len(jobinfolist) >= 8:
                    submit_date_str = jobinfolist[0]
                    numseq = int(jobinfolist[3])
                    jobname = jobinfolist[5]
                    email = jobinfolist[6]
                    method_submission = jobinfolist[7]

            isValidSubmitDate = True
            isValidStartDate = True
            isValidFinishDate = True
            try:
                submit_date = webcom.datetime_str_to_time(submit_date_str)
            except ValueError:
                isValidSubmitDate = False
            start_date_str = ""
            if os.path.exists(starttagfile):
                start_date_str = myfunc.ReadFile(starttagfile).strip()
            try:
                start_date = webcom.datetime_str_to_time(start_date_str)
            except ValueError:
                isValidStartDate = False
            finish_date_str = myfunc.ReadFile(finishtagfile).strip()
            try:
                finish_date = webcom.datetime_str_to_time(finish_date_str)
            except ValueError:
                isValidFinishDate = False

            queuetime = ""
            runtime = ""

            if isValidStartDate and isValidFinishDate:
                runtime = myfunc.date_diff(start_date, finish_date)
            if isValidSubmitDate and isValidStartDate:
                queuetime = myfunc.date_diff(submit_date, start_date)

            row_content = [rank, jobid, jobname[:20], str(numseq), email,
                    queuetime, runtime, submit_date_str, method_submission]
            if info['isSuperUser']:
                row_content.insert(5, ip)
            jobinfo_list.append(row_content)

        info['content'] = jobinfo_list

    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/finished_job.html', info)

#}}}
def get_failed_job(request):#{{{
    info = {}
    set_basic_config(request, info)
    info['header'] = ["No.", "JobID","JobName", "NumSeq", "Email",
            "QueueTime","RunTime", "Date", "Source"]
    if info['isSuperUser']:
        info['header'].insert(5, "Host")

    hdl = myfunc.ReadLineByBlock(info['divided_logfile_query'])
    if hdl.failure:
#         info['errmsg'] = "Failed to retrieve finished job information!"
        info['errmsg'] = ""
        pass
    else:
        finished_job_dict = myfunc.ReadFinishedJobLog(info['divided_logfile_finished_jobid'])
        jobRecordList = []
        lines = hdl.readlines()
        current_time = datetime.now(timezone(TZ))
        while lines != None:
            for line in lines:
                strs = line.split("\t")
                if len(strs) < 7:
                    continue
                ip = strs[2]
                if not info['isSuperUser'] and ip != info['client_ip']:
                    continue

                submit_date_str = strs[0]
                submit_date = webcom.datetime_str_to_time(submit_date_str)
                diff_date = current_time - submit_date
                if diff_date.days > info['MAX_DAYS_TO_SHOW']:
                    continue
                jobid = strs[1]
                rstdir = "%s/%s"%(path_result, jobid)

                if jobid in finished_job_dict:
                    status = finished_job_dict[jobid][0]
                    if status == "Failed":
                        jobRecordList.append(jobid)
                else:
                    failtagfile = "%s/%s"%(rstdir, "runjob.failed")
                    if os.path.exists(rstdir) and os.path.exists(failtagfile):
                        jobRecordList.append(jobid)
            lines = hdl.readlines()
        hdl.close()


        jobinfo_list = []
        rank = 0
        for jobid in jobRecordList:
            rank += 1

            ip = ""
            jobname = ""
            email = ""
            method_submission = ""
            numseq = 1
            submit_date_str = ""

            rstdir = "%s/%s"%(path_result, jobid)
            starttagfile = "%s/runjob.start"%(rstdir)
            failtagfile = "%s/runjob.failed"%(rstdir)

            if jobid in finished_job_dict:
                submit_date_str = finished_job_dict[jobid][0]
                jobname = finished_job_dict[jobid][1]
                ip = finished_job_dict[jobid][2]
                email = finished_job_dict[jobid][3]
                numseq = finished_job_dict[jobid][4]
                method_submission = finished_job_dict[jobid][5]
                submit_date_str = finished_job_dict[jobid][6]
                start_date_str = finished_job_dict[jobid][ 7]
                finish_date_str = finished_job_dict[jobid][8]
            else:
                jobinfofile = "%s/jobinfo"%(rstdir)
                jobinfo = myfunc.ReadFile(jobinfofile).strip()
                jobinfolist = jobinfo.split("\t")
                if len(jobinfolist) >= 8:
                    submit_date_str = jobinfolist[0]
                    numseq = int(jobinfolist[3])
                    jobname = jobinfolist[5]
                    email = jobinfolist[6]
                    method_submission = jobinfolist[7]

            isValidStartDate = True
            isValidFailedDate = True
            isValidSubmitDate = True

            try:
                submit_date = webcom.datetime_str_to_time(submit_date_str)
            except ValueError:
                isValidSubmitDate = False

            start_date_str = ""
            if os.path.exists(starttagfile):
                start_date_str = myfunc.ReadFile(starttagfile).strip()
            try:
                start_date = webcom.datetime_str_to_time(start_date_str)
            except ValueError:
                isValidStartDate = False
            failed_date_str = myfunc.ReadFile(failtagfile).strip()
            try:
                failed_date = webserver_common.datetime_str_to_time(failed_date_str)
            except ValueError:
                isValidFailedDate = False

            queuetime = ""
            runtime = ""

            if isValidStartDate and isValidFailedDate:
                runtime = myfunc.date_diff(start_date, failed_date)
            if isValidSubmitDate and isValidStartDate:
                queuetime = myfunc.date_diff(submit_date, start_date)

            row_content = [rank, jobid, jobname[:20], str(numseq), email,
                    queuetime, runtime, submit_date_str, method_submission]
            if info['isSuperUser']:
                row_content.insert(5, ip)
            jobinfo_list.append(row_content)

        info['content'] = jobinfo_list

    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/failed_job.html', info)
#}}}

def get_help(request):#{{{
    info = {}
    set_basic_config(request, info)
    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/help.html', info)
#}}}
def get_countjob_country(request):#{{{
    info = {}
    set_basic_config(request, info)

    countjob_by_country = "%s/countjob_by_country.txt"%(path_stat)
    lines = myfunc.ReadFile(countjob_by_country).split("\n")
    li_countjob_country = []
    for line in lines: 
        if not line or line[0]=="#":
            continue
        strs = line.split("\t")
        if len(strs) >= 4:
            country = strs[0]
            try:
                numseq = int(strs[1])
            except:
                numseq = 0
            try:
                numjob = int(strs[2])
            except:
                numjob = 0
            try:
                numip = int(strs[3])
            except:
                numip = 0
            li_countjob_country.append([country, numseq, numjob, numip])
    li_countjob_country_header = ["Country", "Numseq", "Numjob", "NumIP"]

    info['li_countjob_country'] = li_countjob_country
    info['li_countjob_country_header'] = li_countjob_country_header

    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/countjob_country.html', info)
#}}}
def get_news(request):#{{{
    info = {}
    set_basic_config(request, info)

    newsfile = "%s/%s/%s"%(SITE_ROOT, "static/doc", "news.txt")
    newsList = []
    if os.path.exists(newsfile):
        newsList = myfunc.ReadNews(newsfile)
    info['newsList'] = newsList
    info['newsfile'] = newsfile
    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/news.html', info)
#}}}
def get_reference(request):#{{{
    info = {}
    set_basic_config(request, info)
    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/reference.html', info)
#}}}
def get_serverstatus(request):#{{{
    info = {}
    set_basic_config(request, info)

    logfile_finished =  "%s/%s/%s"%(SITE_ROOT, "static/log", "finished_job.log")
    logfile_runjob =  "%s/%s/%s"%(SITE_ROOT, "static/log", "runjob_log.log")
    logfile_country_job = "%s/%s/%s"%(path_log, "stat", "country_job_numseq.txt")

# finished sequences submitted by wsdl
# finished sequences submitted by web

# javascript to show finished sequences of the data (histogram)

# get jobs queued locally (at the front end)
    num_seq_in_local_queue = 0
    cmd = [suq_exec, "-b", suq_basedir, "ls"]
    cmdline = " ".join(cmd)
    try:
        suq_ls_content =  subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        lines = suq_ls_content.split("\n")
        cntjob = 0
        for line in lines:
            if line.find("runjob") != -1:
                cntjob += 1
        num_seq_in_local_queue = cntjob
    except subprocess.CalledProcessError, e:
        date_str = time.strftime(g_params['FORMAT_DATETIME'])
        myfunc.WriteFile("[%s] %s\n"%(date_str, str(e)), gen_errfile, "a", True)

# get jobs queued remotely ()
    runjob_dict = {}
    if os.path.exists(logfile_runjob):
        runjob_dict = myfunc.ReadRunJobLog(logfile_runjob)
    cntseq_in_remote_queue = 0
    for jobid in runjob_dict:
        li = runjob_dict[jobid]
        numseq = li[4]
        rstdir = "%s/%s"%(path_result, jobid)
        finished_idx_file = "%s/finished_seqindex.txt"%(rstdir)
        if os.path.exists(finished_idx_file):
            num_finished = len(myfunc.ReadIDList(finished_idx_file))
        else:
            num_finished = 0

        cntseq_in_remote_queue += (numseq - num_finished)



# get number of finished seqs
    allfinishedjoblogfile = "%s/all_finished_job.log"%(path_log)
    allfinished_job_dict = {}
    user_dict = {} # by IP
    if os.path.exists(allfinishedjoblogfile):
        allfinished_job_dict = myfunc.ReadFinishedJobLog(allfinishedjoblogfile)
    total_num_finished_seq = 0
    numjob_wed = 0
    numjob_wsdl = 0
    startdate = ""
    submitdatelist = []
    iplist = []
    countrylist = []
    for jobid in allfinished_job_dict:
        li = allfinished_job_dict[jobid]
        try:
            numseq = int(li[4])
        except:
            numseq = 1
        try:
            submitdatelist.append(li[6])
        except:
            pass
        try:
            method_submission = li[5]
        except:
            method_submission = ""
        try:
            iplist.append(li[2])
        except:
            pass
        ip = ""
        try:
            ip = li[2]
        except:
            pass


        if method_submission == "web":
            numjob_wed += 1
        elif method_submission == "wsdl":
            numjob_wsdl += 1

        if ip != "" and ip != "All" and ip != "127.0.0.1":

            if not ip in user_dict:
                user_dict[ip] = [0,0] #[num_job, num_seq]
            user_dict[ip][0] += 1
            user_dict[ip][1] += numseq

        total_num_finished_seq += numseq

    submitdatelist = sorted(submitdatelist, reverse=False)
    if len(submitdatelist)>0:
        startdate = submitdatelist[0].split()[0]

    uniq_iplist = list(set(iplist))

    countjob_by_country = "%s/countjob_by_country.txt"%(path_stat)
    lines = myfunc.ReadFile(countjob_by_country).split("\n")
    li_countjob_country = []
    countrylist = []
    for line in lines: 
        if not line or line[0]=="#":
            continue
        strs = line.split("\t")
        if len(strs) >= 4:
            country = strs[0]
            try:
                numseq = int(strs[1])
            except:
                numseq = 0
            try:
                numjob = int(strs[2])
            except:
                numjob = 0
            try:
                numip = int(strs[3])
            except:
                numip = 0
            li_countjob_country.append([country, numseq, numjob, numip])
            countrylist.append(country)
    uniq_countrylist = list(set(countrylist))

    li_countjob_country_header = ["Country", "Numseq", "Numjob", "NumIP"]


    MAX_ACTIVE_USER = 10
    # get most active users by num_job
    activeuserli_njob_header = ["IP", "Country", "NumJob", "NumSeq"]
    activeuserli_njob = []
    rawlist = sorted(user_dict.items(), key=lambda x:x[1][0], reverse=True)
    cnt = 0
    for i in xrange(len(rawlist)):
        cnt += 1
        ip = rawlist[i][0]
        njob = rawlist[i][1][0]
        nseq = rawlist[i][1][1]
        country = "N/A"
        try:
            match = geolite2.lookup(ip)
            country = pycountry.countries.get(alpha_2=match.country).name
        except:
            pass
        activeuserli_njob.append([ip, country, njob, nseq])
        if cnt >= MAX_ACTIVE_USER:
            break

    # get most active users by num_seq
    activeuserli_nseq_header = ["IP", "Country", "NumJob", "NumSeq"]
    activeuserli_nseq = []
    rawlist = sorted(user_dict.items(), key=lambda x:x[1][1], reverse=True)
    cnt = 0
    for i in xrange(len(rawlist)):
        cnt += 1
        ip = rawlist[i][0]
        njob = rawlist[i][1][0]
        nseq = rawlist[i][1][1]
        country = "N/A"
        try:
            match = geolite2.lookup(ip)
            country = pycountry.countries.get(alpha_2=match.country).name
        except:
            pass
        activeuserli_nseq.append([ip, country, njob, nseq])
        if cnt >= MAX_ACTIVE_USER:
            break

# get longest predicted seq
# get query with most TM helics
# get query takes the longest time
    extreme_runtimelogfile = "%s/stat/extreme_jobruntime.log"%(path_log)
    runtimelogfile = "%s/jobruntime.log"%(path_log)
    infile_runtime = runtimelogfile
    if os.path.exists(extreme_runtimelogfile) and os.path.getsize(extreme_runtimelogfile):
        infile_runtime = extreme_runtimelogfile

    li_longestseq = []
    li_mostTM = []
    li_longestruntime = []
    longestlength = -1
    mostTM = -1
    longestruntime = -1.0

    hdl = myfunc.ReadLineByBlock(infile_runtime)
    if not hdl.failure:
        lines = hdl.readlines()
        while lines != None:
            for line in lines:
                strs = line.split()
                if len(strs) < 8:
                    continue
                runtime = -1.0
                jobid = strs[0]
                seqidx = strs[1]
                try:
                    runtime = float(strs[3])
                except:
                    pass
                numTM = -1
                try:
                    numTM = int(strs[6])
                except:
                    pass
                mtd_profile = strs[4]
                lengthseq = -1
                try:
                    lengthseq = int(strs[5])
                except:
                    pass
                if runtime > longestruntime:
                    li_longestruntime = [jobid, seqidx, runtime, lengthseq, numTM]
                    longestruntime = runtime
                if lengthseq > longestlength:
                    li_longestseq = [jobid, seqidx, runtime, lengthseq, numTM]
                    longestlength = lengthseq
                if numTM > mostTM:
                    mostTM = numTM
                    li_mostTM = [jobid, seqidx, runtime, lengthseq, numTM]
            lines = hdl.readlines()
        hdl.close()

    info['longestruntime_str'] = myfunc.second_to_human(int(longestruntime+0.5))
    info['mostTM_str'] = str(mostTM)
    info['longestlength_str'] = str(longestlength)
    info['total_num_finished_seq'] = total_num_finished_seq
    info['total_num_finished_job'] = len(allfinished_job_dict)
    info['num_unique_ip'] = len(uniq_iplist)
    info['num_unique_country'] = len(uniq_countrylist)
    info['num_finished_seqs_str'] = str(info['total_num_finished_seq'])
    info['num_finished_jobs_str'] = str(info['total_num_finished_job'])
    info['num_finished_jobs_web_str'] = str(numjob_wed)
    info['num_finished_jobs_wsdl_str'] = str(numjob_wsdl)
    info['num_unique_ip_str'] = str(info['num_unique_ip'])
    info['num_unique_country_str'] = str(info['num_unique_country'])
    info['num_seq_in_local_queue'] = num_seq_in_local_queue
    info['num_seq_in_remote_queue'] = cntseq_in_remote_queue
    info['activeuserli_nseq_header'] = activeuserli_nseq_header
    info['activeuserli_njob_header'] = activeuserli_njob_header
    info['li_countjob_country_header'] = li_countjob_country_header
    info['li_countjob_country'] = li_countjob_country
    info['activeuserli_njob_header'] = activeuserli_njob_header
    info['activeuserli_nseq'] = activeuserli_nseq
    info['activeuserli_njob'] = activeuserli_njob
    info['li_longestruntime'] = li_longestruntime
    info['li_longestseq'] = li_longestseq
    info['li_mostTM'] = li_mostTM

    info['startdate'] = startdate
    info['jobcounter'] = webcom.GetJobCounter(info)

    return render(request, 'pred/serverstatus.html', info)
#}}}
def get_example(request):#{{{
    info = {}
    set_basic_config(request, info)
    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/example.html', info)
#}}}
def oldserver(request):#{{{
    url_old_server = ""
    return HttpResponseRedirect(url_old_server);
#}}}
def help_wsdl_api(request):#{{{
    info = {}
    set_basic_config(request, info)
    info['jobcounter'] = webcom.GetJobCounter(info)
    api_script_rtname =  "commonbackend_wsdl"
    extlist = [".py"]
    api_script_lang_list = ["Python"]
    api_script_info_list = []

    for i in xrange(len(extlist)):
        ext = extlist[i]
        api_script_file = "%s/%s/%s"%(SITE_ROOT,
                "static/download/script", "%s%s"%(api_script_rtname,
                    ext))
        api_script_basename = os.path.basename(api_script_file)
        if not os.path.exists(api_script_file):
            continue
        cmd = [api_script_file, "-h"]
        try:
            usage = subprocess.check_output(cmd)
        except subprocess.CalledProcessError, e:
            usage = ""
        api_script_info_list.append([api_script_lang_list[i], api_script_basename, usage])

    info['api_script_info_list'] = api_script_info_list
    return render(request, 'pred/help_wsdl_api.html', info)
#}}}
def download(request):#{{{
    info = {}
    set_basic_config(request, info)

    info['zipfile_wholepackage'] = ""
    info['zipfile_database'] = ""
    info['size_wholepackage'] = ""
    info['size_database'] = ""
    size_wholepackage = 0
    zipfile_wholepackage = ""
    zipfile_database = ""
    if os.path.exists(zipfile_wholepackage):
        info['zipfile_wholepackage'] = os.path.basename(zipfile_wholepackage)
        size_wholepackage = os.path.getsize(os.path.realpath(zipfile_wholepackage))
        size_wholepackage_str = myfunc.Size_byte2human(size_wholepackage)
        info['size_wholepackage'] = size_wholepackage_str
    if os.path.exists(zipfile_database):
        info['zipfile_database'] = os.path.basename(zipfile_database)
        size_database = os.path.getsize(os.path.realpath(zipfile_database))
        size_database_str = myfunc.Size_byte2human(size_database)
        info['size_database'] = size_database_str

    info['jobcounter'] = webcom.GetJobCounter(info)
    return render(request, 'pred/download.html', info)
#}}}

def get_results(request, jobid="1"):#{{{
    resultdict = {}
    set_basic_config(request, resultdict)

    url_scheme = "http://"
    if request.is_secure():
        url_scheme = "https://"

    rstdir = "%s/%s"%(path_result, jobid)
    outpathname = jobid
    resultfile = "%s/%s/%s/%s"%(rstdir, jobid, outpathname, "query.result.txt")
    tarball = "%s/%s.tar.gz"%(rstdir, outpathname)
    zipfile = "%s/%s.zip"%(rstdir, outpathname)
    starttagfile = "%s/%s"%(rstdir, "runjob.start")
    finishtagfile = "%s/%s"%(rstdir, "runjob.finish")
    failtagfile = "%s/%s"%(rstdir, "runjob.failed")
    runjob_errfile = "%s/%s"%(rstdir, "runjob.err")
    query_seqfile = "%s/%s"%(rstdir, "query.fa")
    raw_query_seqfile = "%s/%s"%(rstdir, "query.raw.fa")
    seqid_index_mapfile = "%s/%s/%s"%(rstdir,jobid, "seqid_index_map.txt")
    finished_seq_file = "%s/%s/finished_seqs.txt"%(rstdir, jobid)
    statfile = "%s/%s/stat.txt"%(rstdir, jobid)
    method_submission = "web"

    query_parafile = "%s/query.para.txt"%(rstdir)
    query_para = {}
    if os.path.exists(query_parafile):
        query_para = json.loads(myfunc.ReadFile(query_parafile))

    jobinfofile = "%s/jobinfo"%(rstdir)
    jobinfo = myfunc.ReadFile(jobinfofile).strip()
    jobinfolist = jobinfo.split("\t")
    if len(jobinfolist) >= 8:
        submit_date_str = jobinfolist[0]
        numseq = int(jobinfolist[3])
        jobname = jobinfolist[5]
        email = jobinfolist[6]
        method_submission = jobinfolist[7]
    else:
        submit_date_str = ""
        numseq = 1
        jobname = ""
        email = ""
        method_submission = "web"

    isValidSubmitDate = True
    try:
        submit_date = webcom.datetime_str_to_time(submit_date_str)
    except ValueError:
        isValidSubmitDate = False
    current_time = datetime.now(timezone(TZ))

    resultdict['isResultFolderExist'] = True
    resultdict['errinfo'] = ""
    if os.path.exists(runjob_errfile):
        resultdict['errinfo'] = myfunc.ReadFile(runjob_errfile)

    status = ""
    queuetime = ""
    runtime = ""
    if not os.path.exists(rstdir):
        resultdict['isResultFolderExist'] = False
        resultdict['isFinished'] = False
        resultdict['isFailed'] = True
        resultdict['isStarted'] = False
    elif os.path.exists(failtagfile):
        resultdict['isFinished'] = False
        resultdict['isFailed'] = True
        resultdict['isStarted'] = True
        status = "Failed"
        start_date_str = ""
        if os.path.exists(starttagfile):
            start_date_str = myfunc.ReadFile(starttagfile).strip()
        isValidStartDate = True
        isValidFailedDate = True
        try:
            start_date = webcom.datetime_str_to_time(start_date_str)
        except ValueError:
            isValidStartDate = False
        failed_date_str = myfunc.ReadFile(failtagfile).strip()
        try:
            failed_date = webserver_common.datetime_str_to_time(failed_date_str)
        except ValueError:
            isValidFailedDate = False
        if isValidSubmitDate and isValidStartDate:
            queuetime = myfunc.date_diff(submit_date, start_date)
        if isValidStartDate and isValidFailedDate:
            runtime = myfunc.date_diff(start_date, failed_date)
    else:
        resultdict['isFailed'] = False
        if os.path.exists(finishtagfile):
            resultdict['isFinished'] = True
            resultdict['isStarted'] = True
            status = "Finished"
            isValidStartDate = True
            isValidFinishDate = True
            if os.path.exists(starttagfile):
                start_date_str = myfunc.ReadFile(starttagfile).strip()
            else:
                start_date_str = ""
            try:
                start_date = webcom.datetime_str_to_time(start_date_str)
            except ValueError:
                isValidStartDate = False
            finish_date_str = myfunc.ReadFile(finishtagfile).strip()
            try:
                finish_date = webcom.datetime_str_to_time(finish_date_str)
            except ValueError:
                isValidFinishDate = False
            if isValidSubmitDate and isValidStartDate:
                queuetime = myfunc.date_diff(submit_date, start_date)
            if isValidStartDate and isValidFinishDate:
                runtime = myfunc.date_diff(start_date, finish_date)
        else:
            resultdict['isFinished'] = False
            if os.path.exists(starttagfile):
                isValidStartDate = True
                start_date_str = ""
                if os.path.exists(starttagfile):
                    start_date_str = myfunc.ReadFile(starttagfile).strip()
                try:
                    start_date = webcom.datetime_str_to_time(start_date_str)
                except ValueError:
                    isValidStartDate = False
                resultdict['isStarted'] = True
                status = "Running"
                if isValidSubmitDate and isValidStartDate:
                    queuetime = myfunc.date_diff(submit_date, start_date)
                if isValidStartDate:
                    runtime = myfunc.date_diff(start_date, current_time)
            else:
                resultdict['isStarted'] = False
                status = "Wait"
                if isValidSubmitDate:
                    queuetime = myfunc.date_diff(submit_date, current_time)

    color_status = SetColorStatus(status)

    file_seq_warning = "%s/%s/%s/%s"%(SITE_ROOT, "static/result", jobid, "query.warn.txt")
    seqwarninfo = ""
    if os.path.exists(file_seq_warning):
        seqwarninfo = myfunc.ReadFile(file_seq_warning)

    size_zipfile_str = ""
    if os.path.exists(zipfile):
        size_zipfile = os.path.getsize(zipfile)
        size_zipfile_str = myfunc.Size_byte2human(size_zipfile)

    size_raw_query_seqfile_str = ""
    if os.path.exists(raw_query_seqfile):
        size_raw_query_seqfile = os.path.getsize(raw_query_seqfile)
        size_raw_query_seqfile_str = myfunc.Size_byte2human(size_raw_query_seqfile)

    resultdict['size_zipfile'] = size_zipfile_str
    resultdict['size_raw_query_seqfile'] = size_raw_query_seqfile_str

    resultdict['file_seq_warning'] = os.path.basename(file_seq_warning)
    resultdict['seqwarninfo'] = seqwarninfo
    resultdict['jobid'] = jobid
    resultdict['subdirname'] = "seq_0"
    resultdict['jobname'] = jobname
    resultdict['outpathname'] = os.path.basename(outpathname)
    resultdict['resultfile'] = os.path.basename(resultfile)
    resultdict['tarball'] = os.path.basename(tarball)
    resultdict['zipfile'] = os.path.basename(zipfile)
    resultdict['submit_date'] = submit_date_str
    resultdict['queuetime'] = queuetime
    resultdict['runtime'] = runtime
    resultdict['status'] = status
    resultdict['color_status'] = color_status
    resultdict['numseq'] = numseq
    resultdict['query_seqfile'] = os.path.basename(query_seqfile)
    resultdict['raw_query_seqfile'] = os.path.basename(raw_query_seqfile)
    base_www_url = url_scheme + request.META['HTTP_HOST']
    resultdict['url_result'] = "%s/pred/result/%s"%(base_www_url, jobid)

    sum_run_time = 0.0
    average_run_time = 5.0  # default average_run_time
    num_finished = 0
    cntnewrun = 0
    cntcached = 0
    newrun_table_list = [] # this is used for calculating the remaining time
# get seqid_index_map
    if os.path.exists(finished_seq_file):
        resultdict['index_table_header'] = ["No.", "Length", "PSSM", "HMM",
                "RunTime(s)", "SequenceName", "Source" ]
        index_table_content_list = []
        indexmap_content = myfunc.ReadFile(finished_seq_file).split("\n")
        cnt = 0
        for line in indexmap_content:
            pssm_resultfile_list = []
            hmm_resultfile_list = []
            strs = line.split("\t")
            if len(strs)>=7:
                subfolder = strs[0]
                length_str = strs[1]
                source = strs[4]
                try:
                    if query_para['second_method'] == "psiblast":
                        filelist = [
                                "%s/%s/%s/outputs/%s"%(rstdir, jobid, subfolder, "psiOutput.txt"),
                                "%s/%s/%s/outputs/%s"%(rstdir, jobid, subfolder, "psiPSSM.txt")]
                        for f in filelist:
                            if os.path.exists(f):
                                fsize = os.path.getsize(f)
                                fsize_str = myfunc.Size_byte2human(fsize)
                                pssm_resultfile_list.append((os.path.basename(f), fsize_str))
                    elif query_para['second_method'] == "jackhmmer":
                        filelist = [
                                "%s/%s/%s/outputs/%s"%(rstdir, jobid, subfolder, "hmmOut.txt"),
                                "%s/%s/%s/outputs/%s"%(rstdir, jobid, subfolder, "Alignment.txt"),
                                "%s/%s/%s/outputs/%s"%(rstdir, jobid, subfolder, "tableOut.txt"),
                                "%s/%s/%s/outputs/%s"%(rstdir, jobid, subfolder, "fullOut.txt")]
                        for f in filelist:
                            if os.path.exists(f):
                                fsize = os.path.getsize(f)
                                fsize_str = myfunc.Size_byte2human(fsize)
                                hmm_resultfile_list.append((os.path.basename(f), fsize_str))
                except KeyError:
                    date_str = time.strftime(g_params['FORMAT_DATETIME'])
                    myfunc.WriteFile("[%s] second_method does not find in query_parafile %s\n"%(
                        date_str, query_parafile), gen_errfile, "a", True)
                    pass

                try:
                    runtime_in_sec_str = "%.1f"%(float(strs[5]))
                    if source == "newrun":
                        sum_run_time += float(strs[5])
                        cntnewrun += 1
                    elif source == "cached":
                        cntcached += 1
                except:
                    runtime_in_sec_str = ""
                desp = strs[6]
                rank = "%d"%(cnt+1)
                if cnt < g_params['MAX_ROWS_TO_SHOW_IN_TABLE']:
                    index_table_content_list.append([rank, length_str, pssm_resultfile_list,
                        hmm_resultfile_list, runtime_in_sec_str, desp[:30], subfolder, source])
                if source == "newrun":
                    newrun_table_list.append([rank, subfolder])
                cnt += 1
        if cntnewrun > 0:
            average_run_time = sum_run_time / cntnewrun

        resultdict['index_table_content_list'] = index_table_content_list
        resultdict['indexfiletype'] = "finishedfile"
        resultdict['num_finished'] = cnt
        num_finished = cnt
        resultdict['percent_finished'] = "%.1f"%(float(cnt)/numseq*100)
    else:
        resultdict['index_table_header'] = []
        resultdict['index_table_content_list'] = []
        resultdict['indexfiletype'] = "finishedfile"
        resultdict['num_finished'] = 0
        resultdict['percent_finished'] = "%.1f"%(0.0)

    num_remain = numseq - num_finished

    time_remain_in_sec = numseq * 5 # set default value

    resultdict['num_row_result_table'] = len(resultdict['index_table_content_list'])

    if os.path.exists(starttagfile):
        start_date_str = myfunc.ReadFile(starttagfile).strip()
        isValidStartDate = False
        try:
            start_date_epoch = webcom.datetime_str_to_epoch(start_date_str)
            isValidStartDate = True
        except:
            pass
        if isValidStartDate:
            time_now = time.time()
            cnt_torun = numseq - cntcached #
            win_size = 100
            avg_newrun_time = -1
            if cntnewrun > 0:
                if cntnewrun-1-win_size > 0:
                    idx_firstinwindow = cntnewrun - 1 -win_size
                    numjob_in_window = win_size
                else:
                    idx_firstinwindow = 0
                    numjob_in_window = cntnewrun

                jobid_firstinwindow = newrun_table_list[idx_firstinwindow][1]
                seqfile_firstinwindow = "%s/%s/%s/%s"%(rstdir, jobid, jobid_firstinwindow, "seq.fa")
                if os.path.exists(seqfile_firstinwindow):
                    modtime_first = os.path.getmtime(seqfile_firstinwindow)
                    avg_newrun_time = (time_now - modtime_first)/numjob_in_window

            if cntnewrun <= 0 or avg_newrun_time < 0:
                time_remain_in_sec = cnt_torun * g_params['AVERAGE_RUNTIME_PER_SEQ_IN_SEC']
            else:
                time_remain_in_sec = int(avg_newrun_time*cnt_torun+0.5)

    time_remain = myfunc.second_to_human(int(time_remain_in_sec+0.5))
    resultdict['time_remain'] = time_remain

    if os.path.exists(rstdir):
        resultdict['isResultFolderExist'] = True
    else:
        resultdict['isResultFolderExist'] = False

    if numseq <= 1:
        if method_submission == "web":
            resultdict['refresh_interval'] = 2
        else:
            resultdict['refresh_interval'] = 5
    else:
        #resultdict['refresh_interval'] = numseq * 2
        addtime = int(math.sqrt(max(0,min(num_remain, num_finished))))+1
        resultdict['refresh_interval'] = average_run_time + addtime

    resultdict['MAX_ROWS_TO_SHOW_IN_TABLE'] = g_params['MAX_ROWS_TO_SHOW_IN_TABLE']

    resultdict['jobcounter'] = webcom.GetJobCounter(resultdict)
    return render(request, 'pred/get_results.html', resultdict)
#}}}
def get_results_eachseq(request, jobid="1", seqindex="1"):#{{{
    resultdict = {}
    set_basic_config(request, resultdict)

    url_scheme = "http://"
    if request.is_secure():
        url_scheme = "https://"
    resultdict['isAllNonTM'] = True

    rstdir = "%s/%s"%(path_result, jobid)
    outpathname = jobid

    jobinfofile = "%s/jobinfo"%(rstdir)
    jobinfo = myfunc.ReadFile(jobinfofile).strip()
    jobinfolist = jobinfo.split("\t")
    if len(jobinfolist) >= 8:
        submit_date_str = jobinfolist[0]
        numseq = int(jobinfolist[3])
        jobname = jobinfolist[5]
        email = jobinfolist[6]
        method_submission = jobinfolist[7]
    else:
        submit_date_str = ""
        numseq = 1
        jobname = ""
        email = ""
        method_submission = "web"

    status = ""

    resultdict['jobid'] = jobid
    resultdict['subdirname'] = seqindex
    resultdict['jobname'] = jobname
    resultdict['outpathname'] = os.path.basename(outpathname)
    resultdict['status'] = status
    resultdict['numseq'] = numseq
    base_www_url = url_scheme + request.META['HTTP_HOST']

    resultfile = "%s/%s/%s/%s"%(rstdir, outpathname, seqindex, "query.result.txt")

    if os.path.exists(rstdir):
        resultdict['isResultFolderExist'] = True
    else:
        resultdict['isResultFolderExist'] = False


    if os.path.exists(resultfile):
        resultdict['resultfile'] = os.path.basename(resultfile)
    else:
        resultdict['resultfile'] = ""

    resultdict['jobcounter'] = webcom.GetJobCounter(resultdict)
    return render(request, 'pred/get_results_eachseq.html', resultdict)
#}}}

# enabling wsdl service

#{{{ The actual wsdl api
class Container_submitseq(DjangoComplexModel):
    class Attributes(DjangoComplexModel.Attributes):
        django_model = FieldContainer
        django_exclude = ['excluded_field']


class Service_submitseq(ServiceBase):

    @rpc(Unicode,  Unicode, Unicode, Unicode, Unicode, Unicode, _returns=Iterable(Unicode))
# submitted_remote will be called by the daemon
# sequences are submitted one by one by the daemon, but the numseq_of_job is
# for the number of sequences of the whole job submitted to the front end
# isforcerun is set as string, "true" or "false", case insensitive
    def submitjob_remote(ctx, seq="", para_str="", jobname="", email="",#{{{
            numseq_this_user="", isforcerun=""):
        logger = logging.getLogger(__name__)
        seq = seq + "\n" #force add a new line for correct parsing the fasta file

        seqinfo = {}
        query_para = json.loads(para_str)
        is_valid_parameter = True
        if query_para['name_software'] in ['prodres', 'docker_prodres']:
            is_valid_parameter = webcom.ValidateParameter_PRODRES(query_para)
        seqinfo.update(query_para)

        filtered_seq = ""
        if is_valid_parameter:
            filtered_seq = webcom.ValidateSeq(seq, seqinfo, g_params)

        if numseq_this_user != "" and numseq_this_user.isdigit():
            seqinfo['numseq_this_user'] = int(numseq_this_user)
        else:
            seqinfo['numseq_this_user'] = 1

        numseq_str = "%d"%(seqinfo['numseq'])
        warninfo = seqinfo['warninfo']
        if warninfo == "":
            warninfo = "None"
        jobid = "None"
        url = "None"
        if filtered_seq == "":
            errinfo = seqinfo['errinfo']
        else:
            soap_req = ctx.transport.req
            try:
                client_ip = soap_req.META['REMOTE_ADDR']
            except:
                client_ip = ""

            url_scheme = "http://"
            try:
                if soap_req.is_secure():
                    url_scheme = "https://"
            except:
                logger.debug("Failed to run soap_req.is_secure()")
                logger.debug("dir(soap_req):%s"%(str(dir(soap_req))))
                pass

            try:
                hostname = soap_req.META['HTTP_HOST']
            except:
                hostname = ""
#             print client_ip
#             print hostname
            seqinfo['jobname'] = jobname
            seqinfo['email'] = email
            seqinfo['para_str'] = para_str
            seqinfo['date'] = time.strftime(g_params['FORMAT_DATETIME'])
            seqinfo['client_ip'] = client_ip
            seqinfo['hostname'] = hostname
            seqinfo['method_submission'] = "wsdl"
            seqinfo['url_scheme'] = url_scheme
            # for this method, wsdl is called only by the daemon script, isForceRun can be
            # set by the argument
            if isforcerun.upper()[:1] == "T":
                seqinfo['isForceRun'] = True
            else:
                seqinfo['isForceRun'] = False
            jobid = RunQuery_wsdl_local(seq, filtered_seq, seqinfo)
            if jobid == "None":
                errinfo = "Failed to submit your job to the queue\n"+seqinfo['errinfo']
            else:
                log_record = "%s\t%s\t%s\t%s\t%d\t%s\t%s\t%s\n"%(seqinfo['date'], jobid,
                        seqinfo['client_ip'], seqinfo['numseq'],
                        len(seq),seqinfo['jobname'], seqinfo['email'],
                        seqinfo['method_submission'])
                main_logfile_query = "%s/%s/%s"%(SITE_ROOT, "static/log", "submitted_seq.log")
                myfunc.WriteFile(log_record, main_logfile_query, "a")

                divided_logfile_query =  "%s/%s/%s"%(SITE_ROOT, "static/log/divided",
                        "%s_submitted_seq.log"%(seqinfo['client_ip']))
                if seqinfo['client_ip'] != "":
                    myfunc.WriteFile(log_record, divided_logfile_query, "a")

                url = url_scheme + hostname +   g_params['BASEURL'] + "result/%s"%(jobid)

                file_seq_warning = "%s/%s/%s/%s"%(SITE_ROOT, "static/result", jobid, "query.warn.txt")
                if seqinfo['warninfo'] != "":
                    myfunc.WriteFile(seqinfo['warninfo'], file_seq_warning, "a")
                errinfo = seqinfo['errinfo']

        for s in [jobid, url, numseq_str, errinfo, warninfo]:
            yield s
#}}}

    @rpc(Unicode, _returns=Iterable(Unicode))
    def checkjob(ctx, jobid=""):#{{{
        logger = logging.getLogger(__name__)
        rstdir = "%s/%s"%(path_result, jobid)
        soap_req = ctx.transport.req

        url_scheme = "http://"
        try:
            if soap_req.is_secure():
                url_scheme = "https://"
        except:
            logger.debug("Failed to run soap_req.is_secure()")
            logger.debug("dir(soap_req):%s"%(str(dir(soap_req))))
            pass

        hostname = soap_req.META['HTTP_HOST']
        result_url = url_scheme + hostname + "/static/" + "result/%s/%s.zip"%(jobid, jobid)
        status = "None"
        url = ""
        errinfo = ""
        if not os.path.exists(rstdir):
            status = "None"
            errinfo = "Error! jobid %s does not exist."%(jobid)
        else:
            starttagfile = "%s/%s"%(rstdir, "runjob.start")
            finishtagfile = "%s/%s"%(rstdir, "runjob.finish")
            failtagfile = "%s/%s"%(rstdir, "runjob.failed")
            runjob_errfile = "%s/%s"%(rstdir, "runjob.err")
            if os.path.exists(failtagfile):
                status = "Failed"
                errinfo = ""
                if os.path.exists(runjob_errfile):
                    errinfo = myfunc.ReadFile(runjob_errfile)
            elif os.path.exists(finishtagfile):
                status = "Finished"
                url = result_url
                errinfo = ""
            elif os.path.exists(starttagfile):
                status = "Running"
            else:
                status = "Wait"
        for s in [status, url, errinfo]:
            yield s
#}}}
    @rpc(Unicode, _returns=Iterable(Unicode))
    def deletejob(ctx, jobid=""):#{{{
        rstdir = "%s/%s"%(path_result, jobid)
        status = "None"
        errinfo = ""
        try: 
            shutil.rmtree(rstdir)
            status = "Succeeded"
        except OSError as e:
            errinfo = str(e)
            status = "Failed"
        for s in [status, errinfo]:
            yield s
#}}}

class ContainerService_submitseq(ServiceBase):
    @rpc(Integer, _returns=Container_submitseq)
    def get_container(ctx, pk):
        try:
            return FieldContainer.objects.get(pk=pk)
        except FieldContainer.DoesNotExist:
            raise ResourceNotFoundError('Container_submitseq')

    @rpc(Container_submitseq, _returns=Container_submitseq)
    def create_container(ctx, container):
        try:
            return FieldContainer.objects.create(**container.as_dict())
        except IntegrityError:
            raise ResourceAlreadyExistsError('Container_submitseq')

class ExceptionHandlingService_submitseq(DjangoServiceBase):
    """Service for testing exception handling."""

    @rpc(_returns=Container_submitseq)
    def raise_does_not_exist(ctx):
        return FieldContainer.objects.get(pk=-1)

    @rpc(_returns=Container_submitseq)
    def raise_validation_error(ctx):
        raise ValidationError('Is not valid.')


app_submitseq = Application([Service_submitseq, ContainerService_submitseq,
    ExceptionHandlingService_submitseq], 'commonbackend.bioinfo.se',
    in_protocol=Soap11(validator='soft'), out_protocol=Soap11())
#wsgi_app_submitseq = WsgiApplication(app_submitseq)

submitseq_service = csrf_exempt(DjangoApplication(app_submitseq))

#}}}
