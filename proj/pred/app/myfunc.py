#!/usr/bin/env python

# Description:
#   A collection of classes and functions used by other programs
#
# Author: Nanjiang Shu (nanjiang.shu@scilifelab.se)
#
# Address: Science for Life Laboratory Stockholm, Box 1031, 17121 Solna, Sweden

import sys
import os
import re
import random
import mydb_common
import copy
import subprocess
import requests
import gzip
import time
import datetime
from Bio.PDB.PDBParser import PDBParser
from Bio.PDB.Polypeptide import PPBuilder
FORMAT_DATETIME = "%Y-%m-%d %H:%M:%S %Z"
GAP = "-"
BLOCK_SIZE = 100000 #set a good value for reading text file by block reading

def myopen(filename = "", default_fp = None, mode = "w", isRaise=False):#{{{
    """
    A wrapper of file open function
    """
    if filename != "":
        try:
            fp = open(filename,mode)
            return fp
        except IOError:
            msg = "Failed to open file {} with mode {}"
            print >>sys.stderr, msg.format(filename, mode)
            print >> sys.stderr, "Reset output to", default_fp
            if isRaise:
                raise
            else:
                fp = default_fp
                return fp
    else:
        fp = default_fp
        return fp
#}}}
def myclose(fp):#{{{
    """
    A wrapper of file close function
    """
    try:
        if fp != None and fp != sys.stdout and fp != sys.stderr:
            fp.close()
    except IOError:
        print >> sys.stderr, "Failed to close file stream ", fp
        return 1
#}}}
def my_getopt_str(argv, i):#{{{
    """
    Get a string from the argument list, return the string and the updated
    index to the argument list
    """
    try:
        opt = argv[i+1]
        if opt[0] == "-":
            msg = "Error! option '%s' must be followed by a string"\
                    ", not an option arg."
            print >> sys.stderr, msg%(argv[i])
            sys.exit(1)
        return (opt, i+2)
    except IndexError:
        msg = "Error! option '%s' must be followed by a string"
        print >> sys.stderr, msg%(argv[i])
        sys.exit(1)
#}}}
def my_getopt_int(argv, i):#{{{
    """
    Get an integer value from the argument list, return the integer value and
    the updated index to the argument list
    """
    try:
        opt = argv[i+1]
        if opt[0] == "-":
            msg = "Error! option '%s' must be followed by an INT value"\
                    ", not an option arg."
            print >> sys.stderr, msg%(argv[i])
            sys.exit(1)
        try:
            opt = int(opt)
            return (opt, i+2)
        except (ValueError, TypeError):
            msg = "Error! option '%s' must be followed by an INT value"
            print >> sys.stderr, msg%(argv[i])
            sys.exit(1)
    except IndexError:
        msg = "Error! option '%s' must be followed by an INT value"
        print >> sys.stderr, msg%(argv[i])
        sys.exit(1)
#}}}
def my_getopt_float(argv, i):#{{{
    """
    Get an real number from the argument list, return the real number and
    the updated index to the argument list
    """
    try:
        opt = argv[i+1]
        if opt[0] == "-":
            msg = "Error! option '%s' must be followed by an FLOAT value"\
                    ", not an option arg."
            print >> sys.stderr, msg%(argv[i])
            sys.exit(1)
        try:
            opt = float(opt)
            return (opt, i+2)
        except (ValueError, TypeError):
            msg = "Error! option '%s' must be followed by an FLOAT value"
            print >> sys.stderr, msg%(argv[i])
            sys.exit(1)
    except IndexError:
        msg = "Error! option '%s' must be followed by an FLOAT value"
        print >> sys.stderr, msg%(argv[i])
        sys.exit(1)
#}}}
def my_dirname(filename):#{{{
    """
    A wrapper of the function: dirname
    """
    d = os.path.dirname(filename)
    if d == "":
        d = "."
    return d
#}}}
def my_rootname(filename):#{{{
    """
    return the rootname of a given file
    """
    return  os.path.basename(os.path.splitext(filename)[0])
#}}}
def checkfile(f, name="input"):#{{{
    """
    Whether the file name is empty or if the file exists
    """
    if f == "":
        print >> sys.stderr, "%s not set."%(name)
        return 1
    elif not os.path.exists(f):
        print >> sys.stderr, "%s %s does not exist."%(name, f)
        return 1
    else:
        return 0
#}}}
def GetFirstWord(buff, sep=None):#{{{
    """
    Get the first word from a string delimited by the supplied separator
    """
    try:
        return buff.split(sep, 1)[0]
    except IndexError:
        return ""
#}}}
def GetFirstWord1(buff, delimiter = " \t\r,.\n"):#{{{
# this version is only slightly faster when the length of first word is short,
# e.g. < 6 chars and when the delimiter is long. It is suitable for getting
# firstword of an natual language article.
    if buff:
        firstword = ""
        for i in xrange(len(buff)):
            if delimiter.find(buff[i]) < 0:
                firstword += buff[i]
            else:
                break
        return firstword
    else:
        return ""
#}}}
def GetFirstWord2(buff, delimiter = " \t\r,.\n"):#{{{
# for testing
# almost the same speed as GetFirstWord1
    if buff:
        m = len(delimiter)
        plist = []
        for de in delimiter:
            plist.append(len(buff.partition(de)[0]))
        return buff[:min(plist)]
    else:
        return ""
#}}}

def FillSymmetricMatrix(matrix, N):#{{{
    """
    Fill in the bottom left part of a symmetric matrix, give the upper right
    corner filled. The input matrix is un-changed
    ------
    |+++++
    | ++++
    |  +++
    |   ++
    |    +
    """
    mtx = copy.deepcopy(matrix)
    for i in xrange(N):
        for j in xrange(i+1, N):
            mtx[j][i] = mtx[i][j]
    return mtx
#}}}
def AverageOfFraction(table):#{{{
# given a tabel 
# f11 f12 f13 f14 count1
# f21 f22 f23 f24 count2
# ...
# calculate 
# avgF1 avgF2 avgF3 avgF4 countAll
    if len(table) < 1:
        return []
    numX = len(table)
    numY = len(table[0])
    sumList = [0.0] * (numY-1)
    total = 0.0
    for i in xrange(numX):
        for j in xrange(numY-1):
            sumList[j] += table[i][j]*table[i][numY-1]
        total += table[i][numY-1]
    fracList = [FloatDivision(x,total) for x in sumList]
    fracList.append(total)
    return fracList
#}}}
def FloatDivision(x1, x2):#{{{
    """
    Return the division of two values.
    """
    try:
        return float(x1)/x2
    except ZeroDivisionError:
        return 0.0
#}}}
def uniquelist(li, idfun=None):#{{{
    """
    Return the unique items of a list while keep the order of the original list
    """
    # order preserving
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in li:
        marker = idfun(item)
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result
#}}}
class MyDB: #{{{
# Description:
#   A class to handle a database of dumped data. The content for each query id
#   can be accessed quickly by GetRecord(id)
# variables:
#     indexedIDList  :  list of record IDs
# 
# Functions:
#     GetRecord(id)  : retrieve record for id, 
#                      return None if failed
#     GetAllRecord() : retrieve all records in the form of list

    def __init__(self, dbname, index_format = mydb_common.FORMAT_BINARY,#{{{
                    isPrintWarning = False):
#        print "Init", dbname
        self.failure = False
        self.index_type = mydb_common.TYPE_DICT
        self.dbname = dbname
        self.dbname_basename = os.path.basename(dbname)
        self.dbname_dir = os.path.dirname(self.dbname)
        self.dbname_dir_full = os.path.realpath(self.dbname_dir)
        self.dbname_full = self.dbname_dir_full + os.sep + self.dbname_basename
        self.index_format = index_format
        self.isPrintWarning = isPrintWarning
        self.fpdbList = []
        (self.indexfile, self.index_format) =\
                        mydb_common.GetIndexFile(self.dbname_full,
                                        self.index_format)
        if self.indexfile != "":
            (self.indexList, self.headerinfo, self.dbfileindexList) =\
                            self.ReadIndex(self.indexfile, self.index_format)
            if self.indexList == None:
                msg = "Failed to read index file {}. Init database {} failed."
                print >> sys.stderr, msg.format(self.indexfile,
                                self.dbname_full)
                self.failure = True
                return None
            if self.OpenDBFile() == 1:
                self.failure = True
                return None
            self.indexedIDList = self.indexList[0]
            self.numRecord = len(self.indexedIDList)
            if self.index_type == mydb_common.TYPE_DICT:
                self.indexDict = {}
                for i in xrange(self.numRecord):
                        self.indexDict[self.indexedIDList[i]] = i
        else:
            msg = "Failed to find indexfile for db {}"
            print >> sys.stderr, msg.format(dbname)
            self.failure = True
            return None
          #}}}
    def __del__(self):#{{{
#        print "Leaving %s"%(self.dbname)
        try: 
            for fp in self.fpdbList:
                fp.close()
            return 0
        except IOError:
            print >> sys.stderr, "Failed to close db file"
        #}}}
    def ReadIndex(self, indexfile, index_format):#{{{
# return (headerinfo, dbfileindexList, index, idList)
# return (indexList, headerinfo, dbfileindexList)
        if index_format == mydb_common.FORMAT_TEXT:
            return mydb_common.ReadIndex_text(indexfile, self.isPrintWarning)
        else:
            return mydb_common.ReadIndex_binary(indexfile, self.isPrintWarning)
#}}}
    def OpenDBFile(self):#{{{
        for i in self.dbfileindexList:
            dbfile = self.dbname_full + "%d.db"%(i)
            try:
                self.fpdbList.append(open(dbfile,"rb"))
            except IOError:
                print >> sys.stderr, "Failed to read dbfile %s"%(dbfile)
                return 1
        return 0
#}}}
    def GetRecordByIndexList(self, record_id):#{{{
        try:
            idxItem = self.indexedIDList.index(record_id);
            fpdb = self.fpdbList[self.indexList[1][idxItem]];
            fpdb.seek(self.indexList[2][idxItem]);
            data = fpdb.read(self.indexList[3][idxItem]);
            return data
        except (IndexError, IOError):
            print >> sys.stderr, "Failed to retrieve record %s"%(record_id)
            return None
#}}}
    def GetRecordByIndexDict(self, record_id):#{{{
        try:
            idxItem = self.indexDict[record_id]
            fpdb = self.fpdbList[self.indexList[1][idxItem]];
            fpdb.seek(self.indexList[2][idxItem]);
            data = fpdb.read(self.indexList[3][idxItem]);
            return data
        except (KeyError, IndexError, IOError):
            print >> sys.stderr, "Failed to retrieve record %s"%(record_id)
            return None
#}}}
    def GetRecord(self, record_id):#{{{
        if self.index_type == mydb_common.TYPE_LIST:
            return self.GetRecordByIndexList(record_id)
        elif self.index_type == mydb_common.TYPE_DICT:
            return self.GetRecordByIndexDict(record_id)
#}}}
    def GetAllRecord(self): #{{{
        recordList = []
        for idd in self.idList:
            recordList.append(self.GetRecord(idd))
        return recordList
    def close(self):#{{{
        try: 
            for fp in self.fpdbList:
                fp.close()
            return 0
        except IOError:
            print >> sys.stderr, "Failed to close db file"
            return 1
        #}}}
    #}}}
#}}}

class ReadLineByBlock:#{{{
# Description: readlines by BLOCK reading, end of line is not included in each
#              line. Empty lines are not ignored 
#              reading lines at about 3 times faster than normal readline()
# Function:
#   readlines()
#   close()
#
# Usage:
# handel = ReadLineByBlock(infile)
# if handel.failure:
#   print "Failed to init ReadLineByBlock for file", infile
#   return 1
# lines = handel.readlines()
# while lines != None:
#       do_something
#       lines = handel.readlines()
    def __init__(self, infile, BLOCK_SIZE=100000):#{{{
        self.failure = False
        self.filename = infile
        self.BLOCK_SIZE = BLOCK_SIZE
        self.isEOFreached = False
        try: 
            self.fpin = open(infile, "rb")
        except IOError:
            print >> sys.stderr, "Failed to read file %s"%(self.filename)
            self.failure = True
            return None
        self.unprocessedBuff = ""
#}}}
    def __del__(self):#{{{
        try:
            self.fpin.close()
        except AttributeError:
            pass
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def close(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def readlines(self):#{{{
        if self.isEOFreached and not self.unprocessedBuff:
            return None
        else:
            buff = self.fpin.read(self.BLOCK_SIZE)
            if not buff:
                self.isEOFreached = True
            if self.unprocessedBuff:
                buff = self.unprocessedBuff + buff

            strs = buff.split('\n')
            numStrs = len(strs)
            if not self.isEOFreached:
                self.unprocessedBuff = strs[numStrs-1]
                return strs[:numStrs-1]
            else:
                self.unprocessedBuff = ""
                return strs
#}}}
#}}}

def mpa2seq(mpa, char_gap="-"):#{{{
    """
    convert mpa record to seq
    """
    try:
        li = []
        for item in mpa['data']:
            if type(item) is tuple:
                li.append(char_gap*(item[1]-item[0]))
            else:
                li.append(item)
        return "".join(li)
    except KeyError:
        print >> sys.stderr, "mpa empty"
        return ""
#}}}

class MySeq:#{{{
    def __init__(self, seqid="", description="", seq=""):
        self.seqid = seqid
        self.description = description
        self.seq = seq
#}}}

class MyMPASeq:#{{{
    def __init__(self, seqid="", description="", mpa={}):
        self.seqid = seqid
        self.description = description
        self.mpa = mpa
#}}}

class ReadFastaByBlock:#{{{
# Description: Read fasta seq by BLOCK reading, 
# Function: 
#   readseq()
#   close()
#
# ChangeLog 2016-11-08
#   support reading gzipped file directly, the gzip file is identified if the
#   file extension is gz
#
# Usage:
# handel = ReadFastaByBlock(infile)
# if handel.failure:
#   print "Failed to init ReadLineByBlock for file", infile
#   return 1
# recordList = handel.readseq()
# while recordList != None:
#       do_something
#       recordList = handel.readseq()
    def __init__(self, infile, method_seqid=1, method_seq=1, BLOCK_SIZE=100000):#{{{
        self.failure = False
        self.filename = infile
        self.BLOCK_SIZE = BLOCK_SIZE
        self.isEOFreached = False
        self.method_seqid = method_seqid
        self.method_seq = method_seq
        if infile.endswith('.gz'):
            self.filetype = 'gzip'
        else:
            self.filetype = 'text'

        if self.filetype == 'text':
            try: 
                self.fpin = open(infile, "rb")
            except IOError:
                print >> sys.stderr, "Failed to read file %s"%(self.filename)
                self.failure = True
                return None
        elif self.filetype == 'gzip':
            try: 
                self.fpin = gzip.open(infile, "rb")
            except IOError:
                print >> sys.stderr, "Failed to read file %s"%(self.filename)
                self.failure = True
                return None
        else:
            print >> sys.stderr, "Unrecognized filetype for the inputfile %s"%(self.filename)
            self.failure = True
            return None

        self.unprocessedBuff = ""
#}}}
    def __del__(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def close(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def readseq(self):#{{{
        if self.isEOFreached and not self.unprocessedBuff:
            return None
        else:
            buff = self.fpin.read(self.BLOCK_SIZE)
            if not buff:
                self.isEOFreached = True
            if self.unprocessedBuff:
                buff = self.unprocessedBuff + buff

            tmpRecordList = []
            self.unprocessedBuff = ReadFastaFromBuffer(buff, tmpRecordList,
                    self.isEOFreached, self.method_seqid, self.method_seq)
            recordList = []
            for rd in tmpRecordList:
                rdc = MySeq(rd[0], rd[1], rd[2])
                recordList.append(rdc)
            return recordList
#}}}
#}}}

class ReadUniprotDatByBlock:#{{{
# Description: Read the uniprot dat file by block reading
# Function: 
#   readseq()
#   close()
#
#   support reading gzipped file directly, the gzip file is identified if the
#   file extension is gz
#
# Usage:
# handel = ReadUniprotDatByBlock(infile)
# if handel.failure:
#   print "Failed to init ReadUniprotDatByBlock for file", infile
#   return 1
# recordList = handel.readseq()
# while recordList != None:
#       do_something
#       recordList = handel.readseq()
# every record includes 
#       aclist
#       seq
#       ID
#       length
#       isRefPro
#       genename
#       organism
#       pfamid
    def __init__(self, infile, BLOCK_SIZE=100000):#{{{
        self.failure = False
        self.filename = infile
        self.BLOCK_SIZE = BLOCK_SIZE
        self.isEOFreached = False
        if infile.endswith('.gz'):
            self.filetype = 'gzip'
        else:
            self.filetype = 'text'

        if infile.find("sprot") != -1:
            self.datatype = "sp"
        elif infile.find("trembl") != -1:
            self.datatype = "tr"
        else:
            self.datatype = ""

        if self.filetype == 'text':
            try: 
                self.fpin = open(infile, "rb")
            except IOError:
                print >> sys.stderr, "Failed to read file %s"%(self.filename)
                self.failure = True
                return None
        elif self.filetype == 'gzip':
            try: 
                self.fpin = gzip.open(infile, "rb")
            except IOError:
                print >> sys.stderr, "Failed to read file %s"%(self.filename)
                self.failure = True
                return None
        else:
            print >> sys.stderr, "Unrecognized filetype for the inputfile %s"%(self.filename)
            self.failure = True
            return None

        self.unprocessedBuff = ""
#}}}
    def __del__(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def close(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}

    def ExtractFromUniprotDat(self, recordContent):#{{{
        record = {}
        lines = recordContent.split("\n")
        numLine = len(lines)
        i = 0
        # AC can be multiple lines
        str_accession = ""     # AC
        str_genename = ""      # GN
        str_organism = ""      # OS
        str_definition = ""    # DE
        protein_existence = "" # PE protein existence
        sequence_version = ""  #SV
        seqid = ""
        sequence_name = ""
        seq = ""
        pfamidList = [] # 
        str_keyword = ""
        length = 0        # from ID record
        str_taxonomic_class = "" # OC, e.g. Archaes, Becteria
        isSeqRecord = False
        for line in lines:
            if len(line) > 2:
                tag = line[0:2]
                if tag == "ID":
                    strs = line[5:].split()
                    nstrs = len(strs)
                    length = int (strs[nstrs-2])
                    seqid = strs[0]
                elif tag == "AC":
                    str_accession += line[5:]
                elif tag == "GN":
                    str_genename += line[5:]
                elif tag == "DE":
                    if line[5:].find("RecName: Full=") == 0:
                        sequence_name = line[5:].split("Full=")[1].strip().rstrip(";").split("{")[0].strip() 
                    elif line[5:].find("Flags") == 0:
                        if line[5:].find("Fragments") != -1:
                            sequence_name += " (Fragments)"
                        elif line[5:].find("Fragment") != -1:
                            sequence_name += " (Fragment)"
                elif tag == "DT":
                    if line.find("sequence version") != -1:
                        sequence_version = line.split()[-1].rstrip('.')
                elif tag == "PE":
                    protein_existence = line[5:].split(':')[0].strip()
                elif tag == "OS":
                    str_organism += line[5:]+" "
                elif tag == "OC":
                    str_taxonomic_class += line[5:]
                elif tag == "KW":
                    str_keyword += line[5:]
                elif tag == "DR":
                    if line[5:].find("Pfam") == 0:
                        strs = line[5:].split(";")
                        pfamidList.append(strs[1].strip())
                elif tag == "SQ":
                    isSeqRecord = True
                elif tag == "  " and isSeqRecord:
                    seq += line[5:].replace(" ", "")

        #accession
        accessionList = str_accession.split(";")
        accessionList = filter(None, accessionList)
        accessionList = [x.strip() for x in accessionList]

        # genename:
        strs = str_genename.split(";")
        strs = filter(None, strs)
        li = []
        for ss in strs:
            sp1 = ss.split("=")
            if len(sp1) == 1:
                ac = sp1[0].strip()
            else:
                ac = sp1[1].strip()
            li.append(ac)
        genename = ";".join(li)

        # organism
        organism = str_organism.strip()
        if not organism.endswith("sp."):
            organism = organism.rstrip(".")

        # taxonomic_class
        taxonomic_class = str_taxonomic_class.split(";")[0]
        taxonomic_class = taxonomic_class.strip(".") # added 2014-08-29, this solved Bacteria. for P07472. 
        isRefPro = False
        if str_keyword.find("Reference proteome") != -1:
            isRefPro = True
        else:
            isRefPro = False

        if len(seq) != length:
            print >> sys.stderr, "Warning! sequence %s len(seq) (%d) != length (%d) "%(";".join(accessionList), len(seq), length)


        if len(accessionList) > 0:
            # the sequence definition used in *.fasta file e.g. uniprot_sprot.fasta
            idd = ""
            if self.datatype != "":
                idd = "%s|%s|%s"%(self.datatype, accessionList[0], seqid)
            else:
                idd = "%s|%s"%(accessionList[0], seqid)

            tmp_seqname = sequence_name.split("{")[0].strip()
#             if tmp_seqname.find("(Fragment") == -1:
#                 tmp_seqname = tmp_seqname.split("(")[0].strip()

            tmp_genename = genename.split(";")[0]
            tmp_genename = tmp_genename.split(",")[0]
            tmp_genename = tmp_genename.split("{")[0]
            tmp_genename = tmp_genename.strip()

            p1 =  organism.find("(isolate")
            p2 =  organism.find("(strain")
            if p1 == -1 and p2 == -1:
                tmp_organism = organism.split("(")[0].strip()
            else:
                p3 = -1
                startp = max(p1,p2)
                p3 = organism[startp+1:].find("(")
                if p3 != -1:
                    tmp_organism = organism[:startp+p3]
                else:
                    tmp_organism = organism
            tmp_organism = tmp_organism.strip()

            sequence_definition = "%s %s"%(idd, tmp_seqname)
            if tmp_organism:
                sequence_definition += " OS=%s"%(tmp_organism)
            if tmp_genename:
                sequence_definition += " GN=%s"%(tmp_genename)
            if protein_existence:
                sequence_definition += " PE=%s"%(protein_existence)
            if sequence_version:
                sequence_definition += " SV=%s"%(sequence_version)

            record['aclist'] = accessionList
            record['ID'] = seqid
            record['length'] = length
            record['genename'] = genename
            record['sequence_version'] = sequence_version
            record['protein_existence'] = protein_existence
            record['organism'] = organism
            record['taxonomic_class'] = taxonomic_class
            record['isRefPro'] = isRefPro
            record['pfamidList'] = pfamidList
            record['seq'] = seq
            record['sequence_name'] = sequence_name
            record['sequence_definition'] = sequence_definition
            return record
        else:
            return {}
#}}}
    def ReadUniprotDatFromBuffer(self, buff, recordList, isEOFreached):#{{{
        if not buff:
            return ""
        unprocessedBuffer = ""
        beg = 0
        end = 0
        while 1:
            beg=buff.find("ID ",beg)
            if beg >= 0:
                end=buff.find("\n//",beg+1)
                if end >= 0:
                    recordContent = buff[beg:end]
                    record = self.ExtractFromUniprotDat(recordContent)
                    if record != {}:
                        recordList.append(record)
                    beg = end
                else:
                    unprocessedBuffer = buff[beg:]
                    break
            else:
                unprocessedBuffer = buff[end:]
                break
        if isEOFreached and unprocessedBuffer:
            recordContent = unprocessedBuffer
            record = self.ExtractFromUniprotDat(recordContent)
            if record != {}:
                recordList.append(record)
            unprocessedBuffer = ""
        return unprocessedBuffer
#}}}
    def readseq(self):#{{{
        if self.isEOFreached and not self.unprocessedBuff:
            return None
        else:
            buff = self.fpin.read(self.BLOCK_SIZE)
            if not buff:
                self.isEOFreached = True
            if self.unprocessedBuff:
                buff = self.unprocessedBuff + buff

            tmpRecordList = []
            self.unprocessedBuff = self.ReadUniprotDatFromBuffer(buff,
                    tmpRecordList, self.isEOFreached)
            recordList = []
            for rd in tmpRecordList:
                recordList.append(rd)
            return recordList
#}}}
#}}}

class ReadMPAByBlock:#{{{
# Description: Read MSA in MPA format by BLOCK reading, 
# Function: 
#   readseq()
#   close()
#
# Usage:
# handel = ReadFastaByBlock(infile)
# if handel.failure:
#   print "Failed to init ReadLineByBlock for file", infile
#   return 1
# recordList = handel.readseq()
# while recordList != None:
#       do_something
#       recordList = handel.readseq()
    def __init__(self, infile, method_seqid=1, method_seq=1, BLOCK_SIZE=100000):#{{{
        self.failure = False
        self.filename = infile
        self.BLOCK_SIZE = BLOCK_SIZE
        self.isEOFreached = False
        self.method_seqid = method_seqid
        self.method_seq = method_seq
        try: 
            self.fpin = open(infile, "rb")
        except IOError:
            print >> sys.stderr, "Failed to read file %s"%(self.filename)
            self.failure = True
            return None
        self.unprocessedBuff = ""
#}}}
    def __del__(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def close(self):#{{{
        try:
            self.fpin.close()
        except IOError:
            print >> sys.stderr, "Failed to close file %s"%(self.filename)
            return 1
#}}}
    def readseq(self):#{{{
        if self.isEOFreached and not self.unprocessedBuff:
            return None
        else:
            buff = self.fpin.read(self.BLOCK_SIZE)
            if not buff:
                self.isEOFreached = True
            if self.unprocessedBuff:
                buff = self.unprocessedBuff + buff

            tmpRecordList = []
            self.unprocessedBuff = ReadMPAFromBuffer(buff, tmpRecordList,
                    self.isEOFreached, self.method_seqid, self.method_seq)
            recordList = []
            for rd in tmpRecordList:
                rdc = MyMPASeq(rd[0], rd[1], rd[2])
                recordList.append(rdc)
            return recordList
#}}}
#}}}

# Other functions
def ReadIDList(infile, delim=None):#{{{
    """
    Read a file containing a list of sequence IDs.
    """
    try:
        fpin = open(infile,"r")
        li = fpin.read().split(delim)
        fpin.close()
        if delim != None:
            li = [x.strip() for x in li]
        return li
    except IOError:
        print "Failed to read idlistfile %s"%infile
        return []
#}}}
def ReadIDList2(infile, col=0, delim=None):#{{{
    """
    Read in ID List of a file with lines, delimited by white space of each line
    the col of ID is specified by col
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return []
    lines = hdl.readlines()
    li = []
    while lines != None:
        for line in lines:
            if not line or line[0] == "#":
                continue
            strs = line.split(delim)
            try:
                li.append(strs[col].strip())
            except:
                pass
        lines = hdl.readlines()
    hdl.close()
    return li
#}}}
def WriteFile(content, outfile, mode="w", isFlush=False):#{{{
    try:
        fpout = open(outfile, mode)
        fpout.write(content)
        if isFlush:
            fpout.flush()
        fpout.close()
        return ""
    except IOError:
        return "Failed to write to %s with mode \"%s\""%(outfile, mode)
#}}}
def ReadFile(infile, mode="r"):#{{{
    try:
        fpin = open(infile, mode)
        content = fpin.read()
        fpin.close()
        return content
    except IOError:
        print >> sys.stderr, "Failed to read file %s with mode '%s'"%(infile,
                mode)
        return ""
#}}}

def WriteIDList(idList, outfile):#{{{
    """
    Write a list of sequence IDs to outfile
    """
    try:
        fpout = open(outfile,"w")
        for idd in idList:
            print >> fpout, idd
        fpout.close()
        return 0
    except IOError:
        print "Failed to write to file %s"%outfile
        return 1
#}}}
def ReadListFile(infile, delimiter = "\n"):#{{{
#Note: the whole string of delimiter will be used to separate items
    try:
        fpin = open(infile,"r")
        li = fpin.read().split(delimiter)
        fpin.close()
        li = [x.strip() for x in li]
        return li
    except IOError:
        msg = "Failed to read listfile {} in function {}"
        print >> sys.stderr, msg.format(infile,
                sys._getframe().f_code.co_name)
        return []
#}}}
def ReadPairList(infile, mode=0):#{{{
    """
    Read in file with pairs (one line per record), return pairlist of tuples
    mode 0: non strict, number of items per line can be >=2, and the first two
            items are taken
    mode 1: strict mode, number of items per line should be exactly 2
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return []
    lines = hdl.readlines()
    pairlist = []
    while lines != None:
        for line in lines:
            if not line or line[0] == "#":
                continue
            strs = line.split()
            if ((mode == 0 and len(strs) >= 2) or 
                    (mode == 1 and len(strs) == 2)):
                pairlist.append((strs[0], strs[1]))
            else:
                msg = "broken pair in file %s: line \"%s\""
                print >> sys.stderr, msg %(infile, line)
        lines = hdl.readlines()
    hdl.close()
    return pairlist
#}}}
def ReadFam2SeqidMap(infile):#{{{
    """
    Read pfam to seqid map
    format of the input file
        FAMID numseq list-of-seq-ids
    e.g.
        PF00854 2 seq1 seq2
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return {}
    lines = hdl.readlines()
    pfam2seqidDict = {}
    while lines != None:
        for line in lines:
            line = line.strip()
            if not line or line[0] == "#":
                continue
            strs = line.split()
            if len(strs) > 2:
                pfam2seqidDict[strs[0]] = strs[2:]
            else:
                msg="broken item in file %s: line \"%s\""
                print >> sys.stderr, msg%(infile, line)
        lines = hdl.readlines()
    hdl.close()
    return pfam2seqidDict
#}}}
def ReadPfamScan(infile, evalue_threshold=1e-3):#{{{
    """
    Read output of pfamscan.pl
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return {}
    seqIDPfamScanDict = {}
    lines = hdl.readlines()
    while lines != None:
        for line in lines:
            if not line or line[0] == "#":
                continue
            strs = line.split()
            if len(strs) >= 15:
                try:
                    seqid = GetSeqIDFromAnnotation(strs[0])
                    tmpdict = {}
                    tmpdict['alnBeg'] = int (strs[1])
                    tmpdict['alnEnd'] = int (strs[2])
                    tmpdict['pfamid'] = strs[5].split('.')[0]
                    tmpdict['pfamname'] = strs[6]
                    tmpdict['evalue'] = float(strs[12])
                    evalue = tmpdict['evalue']
                    tmpdict['clanid'] = strs[14]
                    if evalue <= evalue_threshold:
                        if not seqid in seqIDPfamScanDict:
                            seqIDPfamScanDict[seqid] = []
                        seqIDPfamScanDict[seqid].append(tmpdict)
                except (IndexError, ValueError):
                    msg = "Error in pfamscan file %s at line \"%s\""
                    print >> sys.stderr, msg%(infile, line)
                    pass
        lines = hdl.readlines()
    hdl.close()
    return seqIDPfamScanDict
#}}}
def ReadIDPathMapDict(infile):#{{{
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return {}
    dt = {}
    lines = hdl.readlines()
    while lines != None:
        for line in lines:
            if not line or  line[0] == "#":
                continue
            strs = line.split()
            if len(strs) == 2:
                dt[strs[0]] = strs[1]
        lines = hdl.readlines()
    return dt
#}}}

def GenerateRandomPair(numSample, max_numpair, rand_seed = None):#{{{
    """
    Generate random pairs given the number of samples
    """
    totalNumPair = numSample*(numSample-1)/2
    selectedPairSet = set([])
    adp = selectedPairSet.add
    cntSel = 0
    cntSelectedPair = 0
    random.seed(rand_seed);
    while 1:
        cntSel += 1
        if cntSel > 10:
            break
        idx1 = random.randint(0,numSample-1)
        idx2 = random.randint(0,numSample-1)
        if idx1 == idx2: 
            continue
        pair = (min ([idx1,idx2]), max([idx1,idx2]) )
        if pair in selectedPairSet:
            continue
        adp(pair)
        cntSel=0
        cntSelectedPair += 1
        if cntSelectedPair >= max_numpair:
            break
        if cntSelectedPair >= totalNumPair:
            break
    return list(selectedPairSet)
#}}}
def GenerateRandomPair_no_repeat_use(numSample, max_numpair, rand_seed):#{{{
    """
    Generate random pairs from the given list
    one id is used only once
    """
    li = range(numSample)
    selectedPairList = []
    random.seed(rand_seed);
    while 1:
        if len(li) < 2:
            break
        pair = random.sample(li, 2)
        pair = (min(pair), max(pair))
        selectedPairList.append(pair)
        li.remove(pair[0])
        li.remove(pair[1])
        if len(selectedPairList) >= max_numpair:
            break
    return selectedPairList
#}}}
def GetSeqIDFromAnnotation(line, method_seqid=1):#{{{
    """
    get the ID from the annotation line of the fasta  file
    method_seqid
        0: return the first word in the annotation line
        1: more complited way, default: 1
    ===updated 2013-03-06
    """
    if not line or line.lstrip == "" or line.lstrip() == ">":
        return ""

    if method_seqid == 0:
        return line.partition(" ")[0]
    elif method_seqid == 1:
        seqID = ""
        try:
            line = line.lstrip('>').split()[0]; #get the first word after '>'
            # if the annotation line has |, e.g. >sp|P0AE31|ARTM_ECOL6 Arginine ABC
            # transporter permease
        except:
            return ""
        if line and line.find('|') >= 0:
            strs = line.split("|")
            if (strs[0] in ["sp", "lcl", "tr", "gi", "r", "p"]): 
                seqID = strs[1]
            else : 
                seqID = strs[0]
        else:
            seqID=line
        seqID = seqID.rstrip(",")
        if seqID.find("UniRef") != -1:
            try: 
                ss = seqID.split("_")
                seqID = ss[1]
            except IndexError:
                pass
        return seqID
    else:
        msg = "Unrecognized method (%d) in function %s"
        print >> sys.stderr, msg%(method, sys._getframe().f_code.co_name)
        return ""
#}}}
def GetEvalueFromAnnotation(line):#{{{
    """
    Parsing E-value from the annotation line
    """
    if line:
        m=re.search('evalue *=[^, ]*',line)
        if m: 
            evalue = m.group(0).split('=')[1]
            try:
                return float(evalue)
            except (ValueError, TypeError):
                return None
        else: 
            return None
    return None
#}}}
def GetRLTYFromAnnotation(line):#{{{
    if line:
        m=re.search('rlty *=[^, ]*',line)
        if m: 
            rlty = m.group(0).split('=')[1]
            try:
                return float(rlty)
            except (ValueError, TypeError):
                return None
        else: 
            return None
    return None
#}}}
def GetClusterNoFromAnnotation(line):#{{{
    if line:
        m=re.search('ClusterNo *=[^, ]*',line)
        if m: 
            rlty = m.group(0).split('=')[1]
            try:
                return int(rlty)
            except (ValueError, TypeError):
                return None
        else: 
            return None
    return None
#}}}
def GetNumSeqInClusterFromAnnotation(line):#{{{
    if line:
        m=re.search('numSeqInCluster *=[^, ]*',line)
        if m: 
            rlty = m.group(0).split('=')[1]
            try:
                return int(rlty)
            except (ValueError, TypeError):
                return None
        else: 
            return None
    return None
#}}}
def ReadSingleFasta(inFile):#{{{
# return seqID, annotation, aaSeq
# the leading '>' of the annotation is removed
    try:
        seqID=""
        aaSeq=""
        annotation=""
        fpin = open(inFile, "r")
        lines = fpin.readlines()
        fpin.close()
        for line in lines:
            if line[0] == ">":
                seqID = GetSeqIDFromAnnotation(line)
                annotation = line.lstrip(">").strip()
            else:
                aaSeq+=line.strip()
        return (seqID, annotation, aaSeq)
    except IOError: 
        print >> sys.stderr, "Failed to ReadSingleFasta for ", inFile
        return ("","", "")
#}}}
def GetSingleFastaLength(inFile):#{{{
    """
    return length of the fasta seq (the file should include just one sequence)
    return -1 if failed
    """
    try:
        fpin = open(inFile, "r")
        lines = fpin.readlines()
        fpin.close()
        aaSeq = ""
        for line in lines:
            if line[0] == ">":
                next
            else:
                aaSeq += line.strip()
        return len(aaSeq)
    except IOError: 
        print >> sys.stderr, "GetSingleFastaLength failed for ", inFile
        return -1
#}}}
def old_ReadFasta(inFile):#{{{
#read in all fasta sequences, just the original sequence, do not verify
#annotation is without the leading char '>'
#return (idList, annotationList, seqList)
    try:
        idList=[]
        annotationList=[]
        seqList=[]
        fpin = open(inFile, "r")
        lines = fpin.readlines()
        fpin.close()
        i=0
        while i < len(lines):
            line = lines[i]
            if line[0] == ">":
                seqID = GetSeqIDFromAnnotation(line)
                annoLine = line.lstrip('>').strip()
                seq=""
                i += 1
                while i < len(lines) and lines[i][0] != '>':
                    seq+=lines[i].strip()
                    i=i+1
                idList.append(seqID)
                annotationList.append(annoLine)
                seqList.append(seq)
        return (idList, annotationList, seqList)
    except IOError:
        return ("", "", "")
#}}}
def old_ReadFasta_without_annotation(inFile):#{{{
#read in all fasta sequences, just the original sequence, do not verify
#annotation is without the leading char '>'
#return (idList, seqList)
    try:
        idList=[]
        seqList=[]
        fpin = open(inFile, "r")
        lines = fpin.readlines()
        fpin.close()
        i=0
        while i < len(lines):
            line = lines[i]
            if line[0] == ">":
                seqID = GetSeqIDFromAnnotation(line)
                seq=""
                i += 1
                while i < len(lines) and lines[i][0] != '>':
                    seq+=lines[i].strip()
                    i=i+1
                idList.append(seqID)
                seqList.append(seq)
        return (idList, seqList)
    except IOError:
        return ("", "")
#}}}
def old_ReadFasta_without_id(inFile):#{{{
#read in all fasta sequences, just the original sequence, do not verify
#return (annotationList, seqList)
    try:
        annotationList=[]
        seqList=[]
        fpin = open(inFile, "r")
        lines = fpin.readlines()
        fpin.close()
        i=0
        while i < len(lines):
            line = lines[i]
            if line[0] == ">":
                annoLine = line.lstrip('>').strip()
                seq=""
                i += 1
                while i < len(lines) and lines[i][0] != '>':
                    seq+=lines[i].strip()
                    i=i+1
                annotationList.append(annoLine)
                seqList.append(seq)
        return (annotationList, seqList)
    except IOError:
        return ("", "")
#}}}
def old_ReadFasta_simple(inFile):#{{{
#read in all fasta sequences, just the original sequence, do not verify
#return seqList
    try:
        seqList = []
        fpin = open(inFile, "r")
        lines = fpin.readlines()
        fpin.close()
        i=0
        while i < len(lines):
            line = lines[i]
            if line[0] == ">":
                seq=""
                i += 1
                while i < len(lines) and lines[i][0] != '>':
                    seq+=lines[i].strip()
                    i=i+1
                seqList.append(seq)
        return seqList
    except IOError:
        return ""
#}}}


def GetSegPos(string, keyC):#{{{
    """
    Get segment of a continue keyC state
    e.g. given a string "0001100022000111100"
    and keyC = '1'
    return [(3,5), (13,17)]
    """
    posList = []
    ex = "(%s+)"%(keyC)
    m = re.finditer(ex,string)
    for i in m:
        posList.append((i.start(0), i.end(0)))
    return posList
#}}}
def GetRemainPos(segPosList, length):#{{{
    remainPosList = []
    num = len(segPosList)
    if num < 1:
        remainPosList.append((0, length))
    else:
        if segPosList[0][0] > 0:
            remainPosList.append((0, segPosList[0][0]))
        for i in xrange(num-1):
            remainPosList.append((segPosList[i][1], segPosList[i+1][0]))
        if segPosList[num-1][1] < length:
            remainPosList.append((segPosList[num-1][1], length))
    return remainPosList
#}}}

def ReadFasta(infile, BLOCK_SIZE=100000):#{{{
    """
    Read sequence file in FASTA format
    """
    idList=[]
    annotationList=[]
    seqList=[]
    fpin = None
    try:
        fpin=open(infile,"rb")
    except IOError:
        print >> sys.stderr, "Failed to read fasta file %s "%(infile)
        return ([], [], [])
    buff = fpin.read(BLOCK_SIZE)
    brokenSeqWithAnnoLine=""; ##for the annotation line broken by BLOCK read
    while buff:
        beg=0
        end=0
        while 1:
            if brokenSeqWithAnnoLine:
                if brokenSeqWithAnnoLine[len(brokenSeqWithAnnoLine)-1] == "\n":
                    end=buff.find(">")
                else:
                    end=buff.find("\n>")
                if end >= 0:
                    seqWithAnno = brokenSeqWithAnnoLine + buff[0:end]

                    idList.append( GetSeqIDFromAnnotation(seqWithAnno[0:seqWithAnno.find('\n')]))
                    annotationList.append(seqWithAnno[0:seqWithAnno.find('\n')].lstrip('>').rstrip('\n'))
                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))

                    brokenSeqWithAnnoLine = ""
                    beg=end
                else:
                    brokenSeqWithAnnoLine += buff
                    break

            beg=buff.find(">",beg)
            end=buff.find("\n>",beg+1)
            if beg >= 0:
                if end >=0:
                    seqWithAnno=buff[beg:end]
                    idList.append( GetSeqIDFromAnnotation(seqWithAnno[0:seqWithAnno.find('\n')]))
                    annotationList.append(seqWithAnno[0:seqWithAnno.find('\n')].lstrip('>').rstrip('\n'))
                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
                    beg=end
                else:
                    brokenSeqWithAnnoLine=buff[beg:]
                    break
            else:
                break
        buff = fpin.read(BLOCK_SIZE)

    if brokenSeqWithAnnoLine:
        seqWithAnno=brokenSeqWithAnnoLine
        idList.append( GetSeqIDFromAnnotation(seqWithAnno[0:seqWithAnno.find('\n')]))
        annotationList.append(seqWithAnno[0:seqWithAnno.find('\n')].lstrip('>').rstrip('\n'))
        seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
    fpin.close()
    return (idList, annotationList, seqList)
#}}}
def ReadFasta_without_annotation(infile, BLOCK_SIZE=100000):#{{{
    idList=[]
    seqList=[]
    fpin = None
    try:
        fpin=open(infile,"rb")
    except IOError:
        print >> sys.stderr, "Failed to read file %s."%(infile)
        return (None, None)
    buff = fpin.read(BLOCK_SIZE)
    brokenSeqWithAnnoLine=""; ##for the annotation line broken by BLOCK read
    while buff:
        beg=0
        end=0
        while 1:
            if brokenSeqWithAnnoLine:
                if brokenSeqWithAnnoLine[len(brokenSeqWithAnnoLine)-1] == "\n":
                    end=buff.find(">")
                else:
                    end=buff.find("\n>")
                if end >= 0:
                    seqWithAnno = brokenSeqWithAnnoLine + buff[0:end]

                    idList.append( GetSeqIDFromAnnotation(seqWithAnno[0:seqWithAnno.find('\n')]))
                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))

                    brokenSeqWithAnnoLine = ""
                    beg=end
                else:
                    brokenSeqWithAnnoLine += buff
                    break

            beg=buff.find(">",beg)
            end=buff.find("\n>",beg+1)
            if beg >= 0:
                if end >=0:
                    seqWithAnno=buff[beg:end]
                    idList.append( GetSeqIDFromAnnotation(seqWithAnno[0:seqWithAnno.find('\n')]))
                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
                    beg=end
                else:
                    brokenSeqWithAnnoLine=buff[beg:]
                    break
            else:
                break
        buff = fpin.read(BLOCK_SIZE)

    if brokenSeqWithAnnoLine:
        seqWithAnno=brokenSeqWithAnnoLine
        idList.append( GetSeqIDFromAnnotation(seqWithAnno[0:seqWithAnno.find('\n')]))
        seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
    fpin.close();   
    return (idList, seqList)
#}}}
def ReadFasta_without_id(infile, BLOCK_SIZE=100000):#{{{
    annotationList=[]
    seqList=[]
    fpin = None
    try:
        fpin=open(infile,"rb")
    except IOError:
        print >> sys.stderr, "Failed to open file %s for read"%(infile)
        return (None, None)
    buff = fpin.read(BLOCK_SIZE)
    brokenSeqWithAnnoLine=""; ##for the annotation line broken by BLOCK read
    while buff:
        beg=0
        end=0
        while 1:
            if brokenSeqWithAnnoLine:
                if brokenSeqWithAnnoLine[len(brokenSeqWithAnnoLine)-1] == "\n":
                    end=buff.find(">")
                else:
                    end=buff.find("\n>")
                if end >= 0:
                    seqWithAnno = brokenSeqWithAnnoLine + buff[0:end]

                    annotationList.append(seqWithAnno[0:seqWithAnno.find('\n')].lstrip('>').rstrip('\n'))
                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))

                    brokenSeqWithAnnoLine = ""
                    beg=end
                else:
                    brokenSeqWithAnnoLine += buff
                    break

            beg=buff.find(">",beg)
            end=buff.find("\n>",beg+1)
            if beg >= 0:
                if end >=0:
                    seqWithAnno=buff[beg:end]
                    annotationList.append(seqWithAnno[0:seqWithAnno.find('\n')].lstrip('>').rstrip('\n'))
                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
                    beg=end
                else:
                    brokenSeqWithAnnoLine=buff[beg:]
                    break
            else:
                break
        buff = fpin.read(BLOCK_SIZE)

    if brokenSeqWithAnnoLine:
        seqWithAnno=brokenSeqWithAnnoLine
        annotationList.append(seqWithAnno[0:seqWithAnno.find('\n')].lstrip('>').rstrip('\n'))
        seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
    fpin.close();
    return (annotationList, seqList)
#}}}
def ReadFasta_simple(infile, BLOCK_SIZE=100000):#{{{
    seqList=[]
    fpin = None
    try:
        fpin=open(infile,"rb")
    except IOError:
        print >> sys.stderr, "Failed to open file %s for read"%(infile)
        return None
    buff = fpin.read(BLOCK_SIZE)
    brokenSeqWithAnnoLine=""; ##for the annotation line broken by BLOCK read
    while buff:
        beg=0
        end=0
        while 1:
            if brokenSeqWithAnnoLine:
                if brokenSeqWithAnnoLine[len(brokenSeqWithAnnoLine)-1] == "\n":
                    end=buff.find(">")
                else:
                    end=buff.find("\n>")
                if end >= 0:
                    seqWithAnno = brokenSeqWithAnnoLine + buff[0:end]

                    seqList.append( seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))

                    brokenSeqWithAnnoLine = ""
                    beg=end
                else:
                    brokenSeqWithAnnoLine += buff
                    break

            beg=buff.find(">",beg)
            end=buff.find("\n>",beg+1)
            if beg >= 0:
                if end >=0:
                    seqWithAnno=buff[beg:end]
                    seqList.append(seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
                    beg=end
                else:
                    brokenSeqWithAnnoLine=buff[beg:]
                    break
            else:
                break
        buff = fpin.read(BLOCK_SIZE)

    if brokenSeqWithAnnoLine:
        seqWithAnno=brokenSeqWithAnnoLine
        seqList.append(seqWithAnno[seqWithAnno.find("\n"):].replace('\n','').replace(' ',''))
    fpin.close();   
    return seqList
#}}}

def ReadPDBTOSP(infile): #{{{
    """
    Read pdbtosp.txt, return two dictionaries
    (pdb2uniprotMap, uniprot2pdbMap)
    data structure of the map
    pdb2uniprotMap[pdbid] = 
    {
        'type':'X-ray',
        'resolution': 2.0
        'uniprotaclist': []
    }

    uniprot2pdbMap[uniprotac] = 
    {
        'pdbid1':
        {
        'type':'X-ray',
        'resolution': 2.0
        }
        'pdbid2':
        {
        'type':'NMR',
        'resolution': -
        }
    }
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return ({},{})
    lines = hdl.readlines()
    pdb2uniprotMap = {}
# example line "15C8  X-ray     2.50 A      IGH1M_MOUSE (P01869), IGKC_MOUSE  (P01837)"
    while lines != None:
        for line in lines:
            if not line:
                continue
            if line[0].isdigit():
                try:
                    strs = line.split()
                    pdbid = strs[0]
                    pdb2uniprotMap[pdbid] = {}
                    pdb2uniprotMap[pdbid]['type'] = strs[1]
                    try:
                        pdb2uniprotMap[pdbid]['resolution'] = float(strs[2])
                    except (TypeError, ValueError):
                        pdb2uniprotMap[pdbid]['resolution'] = -1.0
                    pdb2uniprotMap[pdbid]['uniprotaclist'] = []
                    for j in xrange(5,len(strs),2):
                        uniprotac = strs[j].lstrip('(').rstrip(',').rstrip(')')
                        pdb2uniprotMap[pdbid]['uniprotaclist'].append(uniprotac)
                except (IndexError, TypeError):
                    print >> sys.stderr, "bad line in file %s, line=\"%s\""%(
                            infile, line)
        lines = hdl.readlines()
    hdl.close()

# now creating the uniprot2pdbMap
    uniprot2pdbMap = {}
    for pdbid in pdb2uniprotMap:
        dt = pdb2uniprotMap[pdbid]
        for uniprotac in dt['uniprotaclist']:
            if not uniprotac in uniprot2pdbMap:
                uniprot2pdbMap[uniprotac] = {}
            uniprot2pdbMap[uniprotac][pdbid] = {}
            dt2 = uniprot2pdbMap[uniprotac][pdbid] 
            dt2['type'] = dt['type']
            dt2['resolution'] = dt['resolution']
    return (pdb2uniprotMap, uniprot2pdbMap)
#}}}

def ExtractFromSeqWithAnno(seqWithAnno, method_seqid=1, method_seq=0):#{{{
    """
    Extract information from the record seqWithAnno
    Return (seqID, anno, seq)
    ==updated 2013-03-06
    method_seqid (default: 1):
        0: just get the first word in the description line
        1: more complicated way
    method_seq (default: 1)
        0: simple fasta format
        1: extended fasta format, additional information may be added after
           sequence and enclosed by {}
    """
    seqID = None
    anno = None
    seq = None
    if seqWithAnno and seqWithAnno[0] == '>':
        posAnnoEnd = seqWithAnno.find('\n')
        if posAnnoEnd >= 0:
            anno = seqWithAnno[1:posAnnoEnd]
            seqID = GetSeqIDFromAnnotation(anno, method_seqid)

            seq = seqWithAnno[posAnnoEnd+1:]
            seq = re.sub(r"\s+", '', seq)
            if method_seq == 1:
                if seq.find('{') >= 0:
                    # re is much slower than find
                    seq = re.sub("{.*}", '',seq);  
        else:
            anno = seqWithAnno[1:]
            seqID = GetSeqIDFromAnnotation(anno, method_seqid)
            seq = ""
    return (seqID, anno, seq)

#}}}
def ExtractFromSeqWithAnno_MPA(seqWithAnno, method_seqid=1, method_seq=0):#{{{
    """
    Extract information from the record seqWithAnno
    Return (seqID, anno, mpa)
    method_seqid (default: 1):
        0: just get the first word in the description line
        1: more complicated way
    method_seq (default: 1)
        0: simple fasta format
        1: extended fasta format, additional information may be added after
           sequence and enclosed by {}
    """
    posAnnoEnd = seqWithAnno.find('\n')
    anno = seqWithAnno[1:posAnnoEnd]
    seqID = GetSeqIDFromAnnotation(anno, method_seqid)
    content = seqWithAnno[posAnnoEnd+1:]
    if method_seq == 1:
        if content.find('{') >= 0:
            # re is much slower than find
            content = re.sub("{.*}", '',content)
    strs = content.split()
    mpa = {}
    mpa['data'] = []
    mpa['index_gap'] = [] # index point to the gap segment in the data list
    mpa['index_seq'] = [] # index point to seq segments in the data list
    for i  in xrange(len(strs)):
        ss = strs[i]
        if ss.find("-") > 0:
            strs1 = ss.split("-")
            try:
                b = int(strs1[0])
                e = int(strs1[1])
            except (TypeError, ValueError):
                msg = "Error in reading MPA file, record\n%s"
                print >> sys.stderr, msg%(seqWithAnno)
                return ("", "", {})
            mpa['data'].append((b,e))
            mpa['index_gap'].append(i)
        else:
            mpa['data'].append(ss)
            mpa['index_seq'].append(i)
    return (seqID, anno, mpa)
#}}}
def CountFastaSeq(inFile, BLOCK_SIZE=100000):#{{{
# Return the number of sequences given fasta file
# Created 2012-05-24, updated 2012-05-24, Nanjiang Shu 
    try: 
        cntSeq = 0
        isFirstSeq=True
        isPreviousBuffEndWithNewLine=False
        fpin = open(inFile, "r")
        buff = fpin.read(BLOCK_SIZE)
        while buff:
            if isFirstSeq and buff[0] == '>':
                cntSeq +=1
                isFirstSeq = False
            if isPreviousBuffEndWithNewLine and buff[0] == '>':
                cntSeq += 1
                isPreviousBuffEndWithNewLine = False
            cntSeq += buff.count("\n>")
            if buff[len(buff)-1] == '\n':
                isPreviousBuffEndWithNewLine = True
            buff = fpin.read(BLOCK_SIZE)
        fpin.close()
        return cntSeq
    except IOError:
        print >> sys.stderr, "Failed to read seqfile %s" %inFile
        return -1

#}}}
def ReadFastaFromBuffer(buff,recordList, isEOFreached, #{{{
        method_seqid=1, method_seq=0):
# fixed a bug in ReadFastaFromBuffer for plain text aa seq (without ">")
# and also empty sequence record is not ignored but the seq = ""
# 2015-04-13
    """
    Return (unprocessedBuffer)
    method_seqid (default: 1):
        0: just get the first word in the description line
        1: more complicated way
    method_seq (default: 0)
        0: simple fasta format
        1: extended fasta format, additional information may be added after
           sequence and enclosed by {}
    """
    if not buff:
        return ""
    unprocessedBuffer=""
    beg=0
    end=0
    while 1:
        beg=buff.find(">",beg)
        if beg >= 0:
            end=buff.find("\n>",beg+1)
            if end >=0:
                seqWithAnno=buff[beg:end]
                (seqid, seqanno, seq) =  ExtractFromSeqWithAnno(seqWithAnno, method_seqid, method_seq)
                if not seq is None:
                    recordList.append((seqid, seqanno, seq))
                beg=end
            else:
                unprocessedBuffer = buff[beg:]
                break
        else:
            unprocessedBuffer=buff[end:]
            break
    if isEOFreached and unprocessedBuffer:
        seqWithAnno = unprocessedBuffer
        (seqid, seqanno, seq) =  ExtractFromSeqWithAnno(seqWithAnno, method_seqid, method_seq)
        if not seq is None:
            recordList.append((seqid, seqanno, seq))
        unprocessedBuffer = ""
    return unprocessedBuffer
#}}}
def ReadMPAFromBuffer(buff,recordList, isEOFreached, #{{{
        method_seqid=1, method_seq=0):
    """
    Return (unprocessedBuffer)
    method_seqid (default: 1):
        0: just get the first word in the description line
        1: more complicated way
    method_seq (default: 0)
        0: simple mpa format
        1: extended mpa format, additional information may be added after
           sequence and enclosed by {}
    """
    if not buff:
        return ""
    unprocessedBuffer=""
    beg=0
    end=0
    while 1:
        beg=buff.find(">",beg)
        if beg >= 0:
            end=buff.find("\n>",beg+1)
            if end >=0:
                seqWithAnno=buff[beg:end]
                recordList.append(ExtractFromSeqWithAnno_MPA(seqWithAnno,
                    method_seqid, method_seq))
                beg=end
            else:
                unprocessedBuffer = buff[beg:]
                break
        else:
            unprocessedBuffer=buff[end:]
            break
    if isEOFreached and unprocessedBuffer:
        seqWithAnno = unprocessedBuffer
        recordList.append(ExtractFromSeqWithAnno_MPA(seqWithAnno, method_seqid,
            method_seq))
        unprocessedBuffer = ""
    return unprocessedBuffer
#}}}

def coverage(a1,b1,a2,b2):#{{{
    """
    return the coverage of two intervals
    a1, b1, a2, b2 are integers
    when the return value <=0, it means there is no coverage
    """
    return (min(b1,b2)-max(a1,a2))
#}}}

def isnumeric(s):#{{{
    """
    Determine whether a string is numeric value
    """
    try:
        i = float(s)
        return True
    except (ValueError, TypeError):
        return False
#}}}
def isnumeric_extended(lit):#{{{
#including complex, hex, binary and octal numeric literals
    # Handle '0'
    if lit == '0': 
        return True
    # Hex/Binary
    litneg=lit
    if lit[0] == '-':
        litneg = lit[1:] 
    if litneg[0] == '0':
        if litneg[1] in 'xX':
            try:
                v=int(lit,16)
                return True
            except (ValueError, TypeError):
                return False
        elif litneg[1] in 'bB':
            try:
                v=int(lit,2)
                return True
            except (ValueError, TypeError):
                return False
        else:
            try:
                v=int(lit,8)
                return True
            except ValueError:
                pass
 
    # Int/Float/Complex
    try:
        v=int(lit)
        return True
    except ValueError:
        pass
    try:
        v=float(lit)
        return True
    except ValueError:
        pass
    try:
        v=complex(lit)
        return True
    except ValueError:
        return False
#}}}

def confirm(prompt=None, resp=False):#{{{
    """
    prompts for yes or no response from the user. Returns True for yes and
    False for no.

    'resp' should be set to the default value assumed by the caller when
    user simply types ENTER.

    Example :
        if confirm(prompt='Create Dir', resp=True) == True:
            print "run"
        else:
            print "ignore"
    """
    if prompt is None:
        prompt = 'Confirm'

    if resp:
        prompt = '%s [%s]|%s: ' % (prompt, 'y', 'n')
    else:
        prompt = '%s [%s]|%s: ' % (prompt, 'n', 'y')

    while True:
        ans = raw_input(prompt)
        if not ans:
            return resp
        if ans not in ['y', 'Y', 'n', 'N']:
            print 'please enter y or n.'
            continue
        if ans == 'y' or ans == 'Y':
            return True
        if ans == 'n' or ans == 'N':
            return False
#}}}

def GetFirstTMPosition(topo):#{{{
    """
    return the position of the first TM helix
    return (-1,-1) if no TM helix found
    """
    lengthTopo = len(topo)
    b = topo.find('M',0)
    if b != -1:
        m = re.search('[io]', topo[b+1:])
        if m != None:
            e = m.start(0)+b+1
        else:
            e = lengthTopo
        if topo[e-1] == GAP:
            e = topo[:e-1].rfind('M')+1
        if b == e:
            print "Error! topo[b-30:e+30]=", topo[b-30:e+30]
            return (-1,-1)
        else:
            return (b,e)
    else:
        return (-1,-1)
#}}}
def GetTMPosition(topo):#{{{
    """
    Get position of TM helices given a topology
    this version is much faster (~25 times) than using than finditer
    updated 2011-10-24
    """
    posTM=[]
    lengthTopo=len(topo)
    b=0
    e=0
    while 1:
        b=topo.find('M',e)
        if b != -1:
            m = re.search('[io]', topo[b+1:])
            if m != None:
                e = m.start(0)+b+1
            else:
                e=lengthTopo
            if topo[e-1] == GAP:
                e=topo[:e-1].rfind('M')+1
#           print (b,e)
            if b == e:
                print "Error topo[b-10:e+10]=", topo[b-30:e+30]
                #sys.exit(1)
                return []
            posTM.append((b,e))
        else:
            break
    return posTM
#}}}
def GetSPPosition(topo):#{{{
    """
    Get position of Signal Peptide given a topology
    2015-02-10
    """
    posSP=[]
    b = topo.find('S')
    if b != -1:
        e=topo.rfind('S')+1
        posSP.append((b,e))
    return posSP
#}}}
def GetTMPosition_gapless(topo):#{{{
    """
    Get the position of TM helices given the topology (without gaps)
    The return value is a list of 2-tuples: [ (beg, end), (beg, end)...]
    """
    posTM=[]
    m=re.finditer("(M+)",topo)
    for i in m:
        posTM.append((i.start(0), i.end(0)))
    return posTM
#}}}
def ReadSeqLengthDict(infile):#{{{
    """
    Input:
        seqlen file
    Output:
        seqlenDict:   {'seqid': 134, 'seqid': 393}
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return {}
    dt = {}
    lines = hdl.readlines()
    while lines != None:
        for line in lines:
            if not line or line[0] == "#":
                continue
            strs = line.split()
            if len(strs) == 2:
                seqid = strs[0]
                length = int(strs[1])
                dt[seqid] = length
        lines = hdl.readlines()
    hdl.close()
    return dt
#}}}
def ReadID2IDMap(infile):#{{{
    """
    Input:
        File of the content: id1 mappedid
    Output:
        dict:   {'seqid': mappedid, 'seqid': mappedid}
    """
    hdl = ReadLineByBlock(infile)
    if hdl.failure:
        return {}
    dt = {}
    lines = hdl.readlines()
    while lines != None:
        for line in lines:
            if not line or line[0] == "#":
                continue
            strs = line.split()
            if len(strs) == 2:
                dt[strs[0]] = strs[1]
        lines = hdl.readlines()
    hdl.close()
    return dt
#}}}
def CountTM(topo):#{{{
    """Count the number of TM regions in a topology with or without gaps"""
    return len(GetTMPosition(topo))
#}}}
def PosTM2Topo(posTM, seqLength, NtermState):#{{{
    """
    Get the membrane protein topology by given TM helix segment lists and
    location of N-terminus
    posTM     :  a list of tuples, e.g. [(10,30),(35,44), ...]
                defining TM segments, index start from 0 and end index is not included
    seqLength : length of the sequence
    NtermState: location of the N-terminus, in or out

    return a string defining the topology of TM protein
    """
# ChangeLog 2014-10-10 
# NtermState can be in the format of ["i", "in"], before it was only "i"
    if NtermState == "":
        return ""
    topList = []
    statelist = ["i", "o"]
    idx = 0
    if NtermState in ['i', "in", "IN", "I"]:
        idx = 0
    else:
        idx = 1

    state = statelist[idx]
    if len(posTM) < 1:
        topList += [state]*seqLength
    else:
        for j in xrange(len(posTM)):
            state = statelist[idx%2]
            if j == 0:
                seglen = posTM[j][0]
            else:
                seglen = posTM[j][0] - posTM[j-1][1]
            topList += [state]*seglen
            topList += ['M'] * (posTM[j][1]-posTM[j][0])
            idx += 1
        #print posTM, seqLength
        if posTM[len(posTM)-1][1] < seqLength:
            state = statelist[idx%2]
            topList += [state] * (seqLength - posTM[len(posTM)-1][1])
    top = "".join(topList)
    return top
#}}}

def IsValidEmailAddress(email):#{{{
    match = re.search(r'[\w.-]+@[\w.-]+.\w+', email)
    if match:
        return True
    else:
        return False
#}}}

def wrapseq(seq, size=60):#{{{
    """
    wrap the sequence in to a list of fixed length
    """
    return  [seq[i:i+size] for i in xrange(0, len(seq), size)]
#}}}
def date_diff(older, newer):#{{{
    """
    Returns a humanized string representing time difference

    The output rounds up to days, hours, minutes, or seconds.
    4 days 5 hours returns '4 days'
    0 days 4 hours 3 minutes returns '4 hours', etc...
    """

    timeDiff = newer - older
    days = timeDiff.days
    hours = timeDiff.seconds/3600
    minutes = timeDiff.seconds%3600/60
    seconds = timeDiff.seconds%3600%60

    str = ""
    tStr = ""
    if days > 0:
        if days == 1:   tStr = "day"
        else:           tStr = "days"
        str = str + "%s %s" %(days, tStr)
        return str
    elif hours > 0:
        if hours == 1:  tStr = "hour"
        else:           tStr = "hours"
        str = str + "%s %s" %(hours, tStr)
        return str
    elif minutes > 0:
        if minutes == 1:tStr = "min"
        else:           tStr = "mins"
        str = str + "%s %s" %(minutes, tStr)
        return str
    elif seconds >= 0:
        if seconds <= 1:tStr = "sec"
        else:           tStr = "secs"
        str = str + "%s %s" %(seconds, tStr)
        return str
    else:
        return None
#}}}
def second_to_human(time_in_sec):#{{{
    """
    Returns a humanized string given the time in seconds

    The output rounds up to days, hours, minutes, or seconds.
    4 days 5 hours returns '4 days 5 hours'
    0 days 4 hours 3 minutes returns '4 hours 3 mins', etc...
    """

    days = int(time_in_sec)/3600/24
    hours = int(time_in_sec - 3600*24*days)/3600
    minutes = int(time_in_sec - 3600*24*days - 3600*hours)%3600/60
    seconds = time_in_sec%3600%60

    ss = ""
    tStr = ""
    if days > 0:
        if days == 1:   tStr = "day"
        else:           tStr = "days"
        ss += " %s %s" %(days, tStr)
    if hours > 0:
        if hours == 1:  tStr = "hour"
        else:           tStr = "hours"
        ss += " %s %s" %(hours, tStr)
    if minutes > 0:
        if minutes == 1:tStr = "min"
        else:           tStr = "mins"
        ss += " %s %s" %(minutes, tStr)
    if seconds > 0 or (seconds == 0 and days == 0 and hours == 0 and minutes == 0):
        if seconds <= 1:tStr = "sec"
        else:           tStr = "secs"
        ss += " %g %s" %(seconds, tStr)

    ss = ss.strip()
    if ss != "":
        return ss
    else:
        return None
#}}}


def check_output(*popenargs, **kwargs):#{{{
    r"""Run command with arguments and return its output as a byte string.
    Backported from Python 2.7 as it's implemented as pure python on stdlib.
    >>> check_output(['/usr/bin/python', '--version'])
    Python 2.6.2
    """
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output
#}}}

def IsURLExist(url, timeout=2):#{{{
    try:
        response = requests.get(url,timeout=timeout)
        if response.status_code < 400:
            return True
        else:
            return False
    except:
        return False
#}}}
def Size_human2byte(s):#{{{
    if s.isdigit():
        return int(s)
    else:
        s = s.upper()
        match = re.match(r"([0-9]+)([A-Z]+)", s , re.I)
        if match:
            items = match.groups()
            size = int(items[0])
            if items[1] in ["B"]:
                return size
            elif items[1] in ["K", "KB"]:
                return size*1024
            elif items[1] in ["M", "MB"]:
                return size*1024*1024
            elif items[1] in ["G", "GB"]:
                return size*1024*1024*1024
            else:
                print >> sys.stderr, "Bad maxsize argument:",s
                return -1
        else:
            print >> sys.stderr, "Bad maxsize argument:",s
            return -1

#}}}

def Size_byte2human(size, is_kilobyte_1024=True):#{{{
    #Convert a file size to human-readable form.
    #Keyword arguments:
    #   size -- file size in bytes
    #   a_kilobyte_is_1024_bytes -- if True (default), use multiples of 1024
    #                            if False, use multiples of 1000
    #Returns: string
    SUFFIXES = {1000: ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
                1024: ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']}
    if size < 0:
        msg = "number must be non-negative in function %s"
        print >> sys.stderr, msg%(sys._getframe().f_code.co_name)
        return ""

    multiple = 1024 if is_kilobyte_1024 else 1000
    try:
        for suffix in SUFFIXES[multiple]:
            if size < multiple:
                if float(size) - int(size) < 1e-6:
                    return '{0:.0f} {1}'.format(size, suffix)
                else:
                    return '{0:.1f} {1}'.format(size, suffix)
            size /= multiple
    except ValueError:
        msg = "number too large in function %s"
        print >> sys.stderr, msg%(sys._getframe().f_code.co_name)
        return ""
#}}}

def ArchiveFile(filename, maxsize):#{{{
    """
    Archive the logfile if its size exceeds the limit
    """
    if not os.path.exists(filename):
        print >> sys.stderr, filename,  "does not exist. ignore."
        return 1
    else:
        filesize = os.path.getsize(filename)
        if filesize > maxsize:
            cnt = 0
            zipfile = ""
            while 1:
                cnt += 1
                zipfile = "%s.%d.gz"%(filename, cnt)
                if not os.path.exists(zipfile):
                    break
            # write zip file
            try:
                f_in = open(filename, 'rb')
            except IOError:
                print >> sys.stderr, "Failed to read %s"%(filename)
                return 1
            try:
                f_out = gzip.open(zipfile, 'wb')
            except IOError:
                print >> sys.stderr, "Failed to write to %s"%(zipfile)
                return 1

            f_out.writelines(f_in)
            f_out.close()
            f_in.close()
            print "%s is archived to %s"%(filename, zipfile)
            os.remove(filename)
        return 0
#}}}
def GetSuqPriority(numseq_this_user):#{{{
### the jobs queued for more than one day should have higher priority no matter how many sequences it is
    year = datetime.datetime.today().year
    lastyear = year-1
    epoch_time_lastyear = datetime.datetime.strptime(str(lastyear), '%Y').strftime('%s')
    seconds_since_lastyear = time.time() - float(epoch_time_lastyear) 
    if numseq_this_user > 20000:
        numseq_this_user = 20000
    prio = int(( (1/seconds_since_lastyear*1e10) * 1e6 ) ) - int(numseq_this_user**1.35)
    if prio < 0:
        prio = 0

    return prio
#}}}
def Sendmail(from_email, to_email, subject, bodytext):#{{{
    sendmail_location = "/usr/sbin/sendmail" # sendmail location
    p = os.popen("%s -t" % sendmail_location, "w")
    p.write("From: %s\n" % from_email)
    p.write("To: %s\n" % to_email)
    p.write("Subject: %s\n"%(subject))
    p.write("\n") # blank line separating headers from body
    p.write(bodytext)
    status = p.close()
    if status == None or status == 0 :
        print "Sendmail to %s succeeded"%(to_email)
        return 0
    else:
        print "Sendmail to %s failed with status"%(to_email), status
        return status

#}}}
def ReadFinishedJobLog(infile, status=""):#{{{
    dt = {}
    if not os.path.exists(infile):
        return dt

    hdl = ReadLineByBlock(infile)
    if not hdl.failure:
        lines = hdl.readlines()
        while lines != None:
            for line in lines:
                if not line or line[0] == "#":
                    continue
                strs = line.split("\t")
                if len(strs)>= 10:
                    jobid = strs[0]
                    status_this_job = strs[1]
                    if status == "" or status == status_this_job:
                        jobname = strs[2]
                        ip = strs[3]
                        email = strs[4]
                        try:
                            numseq = int(strs[5])
                        except:
                            numseq = 1
                        method_submission = strs[6]
                        submit_date_str = strs[7]
                        start_date_str = strs[8]
                        finish_date_str = strs[9]
                        dt[jobid] = [status_this_job, jobname, ip, email,
                                numseq, method_submission, submit_date_str,
                                start_date_str, finish_date_str]
            lines = hdl.readlines()
        hdl.close()

    return dt
#}}}
def ReadRunJobLog(infile):#{{{
    dt = {}
    if not os.path.exists(infile):
        return dt

    hdl = ReadLineByBlock(infile)
    if not hdl.failure:
        lines = hdl.readlines()
        while lines != None:
            for line in lines:
                if not line or line[0] == "#":
                    continue
                strs = line.split("\t")
                if len(strs)>= 11:
                    jobid = strs[0]
                    status_this_job = strs[1]
                    jobname = strs[2]
                    ip = strs[3]
                    email = strs[4]
                    try:
                        numseq = int(strs[5])
                    except:
                        numseq = 1
                        pass
                    method_submission = strs[6]
                    submit_date_str = strs[7]
                    start_date_str = strs[8]
                    try:
                        total_numseq_of_user = int(str[9])
                    except:
                        total_numseq_of_user = 1
                        pass
                    try:
                        priority = float(str[10])
                    except:
                        priority = 0
                        pass
                    dt[jobid] = [status_this_job, jobname, ip, email,
                            numseq, method_submission, submit_date_str,
                            start_date_str, total_numseq_of_user, priority]
            lines = hdl.readlines()
        hdl.close()

    return dt
#}}}
def ReadNews(infile):#{{{
# read newsfile
    try:
        fpin = open(infile,"r")
        buff = fpin.read()
        fpin.close()
        newsList = []
        pos = 0
        sizebuff = len(buff)
        while pos < sizebuff:
            b = buff[pos:].find("\n<DATE>")
            if b >= 0:
                e = buff[pos+b+1:].find("\n<DATE>")
                if e < 0:
                    e = sizebuff
            else:
                b = sizebuff

            if b < sizebuff:
                rawtext = buff[pos+b+1:pos+b+1+e]
                lines = rawtext.split("\n")
                status = "" # DATE TITLE CONTENT
                date_str_li = []
                title_li = []
                content_li = []
                for line in lines:
                    if line.find("<DATE>") == 0:
                        status = "DATE"
                    elif line.find("<TITLE>") == 0:
                        status = "TITLE"
                    elif line.find("<CONTENT>") == 0:
                        status = "CONTENT"
                    elif line.find("#") == 0:
                        continue

                    txt = line.lstrip("<%s>"%(status)).strip()
                    if txt != "":
                        if status == "DATE":
                            date_str_li.append(txt)
                        elif status == "TITLE":
                            title_li.append(txt)
                        elif status == "CONTENT":
                            content_li.append(txt)
                date_str = " ".join(date_str_li)
                title = " ".join(title_li)
                content = " ".join(content_li)
                if date_str != "" and title != "":
                    try:
                        st_time = time.strptime(date_str, FORMAT_DATETIME)
                        epoch_time = time.mktime(st_time)
                    except ValueError:
                        epoch_time = 0
                    newsList.append([date_str, title, content, epoch_time])
                pos = pos+b+e
            else:
                pos = sizebuff
        newsList = sorted(newsList, key = lambda x:x[3], reverse=True)
        return newsList
    except IOError:
        print >> sys.stderr, "Failed to read newsfile %s"%(infile)
        return []
#}}}
def IsDNASeq(seq):#{{{
# check whether the sequence is a DNA sequence
    seq = seq.upper()
    alphabet = ["A","C","G","T","U"]
    sumACGT = 0
    sumA = seq.count('A')
    sumC = seq.count('C')
    sumG = seq.count('G')
    sumT = seq.count('T')
    sumU = seq.count('U')

    sumACGT = sumA + sumC + sumG + sumT + sumU
    if (FloatDivision(sumACGT, len(seq)) > 0.75 and sumA > 0 and sumC > 0 and
            sumT > 0 and sumG > 0):
        return True
    else:
        return False
#}}}

def PDB2Seq(pdbfile):# {{{
    """Return a list of sequences given the pdbfile
    """
    seqList = []
    structure = PDBParser().get_structure('', pdbfile)
    ppb=PPBuilder()
    for pp in ppb.build_peptides(structure):
        seqList.append(str(pp.get_sequence()))
    return seqList

# }}}
def week_beg_end(day):#{{{
    """
    Given a date return the date of the 
    beginning_of_week (Monday) and end_of_week
    """
    day_of_week = day.weekday()
    to_beginning_of_week = datetime.timedelta(days=day_of_week)
    beginning_of_week = day - to_beginning_of_week
    to_end_of_week = datetime.timedelta(days=6 - day_of_week)
    end_of_week = day + to_end_of_week
    return (beginning_of_week, end_of_week)
#}}}
def disk_usage(path):#{{{
    """Return disk usage statistics about the given path.
    (total, used, free) in bytes
    """
    try:
        st = os.statvfs(path)
        free = st.f_bavail * st.f_frsize
        total = st.f_blocks * st.f_frsize
        used = (st.f_blocks - st.f_bfree) * st.f_frsize
        return (total, used, free)
    except OSError:
        print sys.stderr, "os.statvfs(%s) failed"%(path)
        return (-1,-1,-1)
#}}}
