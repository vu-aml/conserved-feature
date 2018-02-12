# A part of pdfrw (pdfrw.googlecode.com)
# Copyright (C) 2006-2009 Patrick Maupin, Austin, Texas
# MIT license -- See LICENSE.txt for details

'''
The PdfReader class reads an entire PDF file into memory and
parses the top-level container objects.  (It does not parse
into streams.)  The object subclasses PdfDict, and the
document pages are stored in a list in the pages attribute
of the object.
'''
import gc
import re
import os
import pickle

from .errors import PdfParseError, log
from .tokens import PdfTokens
from .objects import PdfDict, PdfArray, PdfName, PdfObject, PdfIndirect
from .uncompress import uncompress


class PdfReader(PdfDict):

    warned_bad_stream_start = False  # Use to keep from spewing warnings
    warned_bad_stream_end = False  # Use to keep from spewing warnings

    def findindirect(self, objnum, gennum, PdfIndirect=PdfIndirect, int=int):
        ''' Return a previously loaded indirect object, or create
            a placeholder for it.
        '''
        key = int(objnum), int(gennum)
        result = self.indirect_objects.get(key)
        if result is None:
            self.indirect_objects[key] = result = PdfIndirect(key)
            self.deferred_objects.add(key)
            result._loader = self.loadindirect
        return result

    def readarray(self, source, PdfArray=PdfArray):
        ''' Found a [ token.  Parse the tokens after that.
        '''
        specialget = self.special.get
        result = []
        pop = result.pop
        append = result.append

        for value in source:
            if value in ']R':
                if value == ']':
                    break
                generation = pop()
                value = self.findindirect(pop(), generation)
            else:
                func = specialget(value)
                if func is not None:
                    value = func(source)
            append(value)
        return PdfArray(result)

    def readdict(self, source, PdfDict=PdfDict):
        ''' Found a << token.  Parse the tokens after that.
        '''
        specialget = self.special.get
        result = PdfDict()
        next = source.next

        tok = next()
        while tok != '>>':
            if not tok.startswith('/'):
                # Just skip the incorrect /name object.
                source.warning('Expected PDF /name object')
                tok = next()
                continue
            key = tok
            value = next()
            func = specialget(value)
            if func is not None:
                # Just keep working when bad token occurs.
                if func == self.badtoken:
                    tok = value
                    continue
                value = func(source)
                tok = next()
            else:
                tok = next()
                if value.isdigit() and tok.isdigit():
                    if next() != 'R':
                        source.exception(
                            'Expected "R" following two integers')
                    value = self.findindirect(value, tok)
                    tok = next()
            result[key] = value
        return result

    def empty_obj(self, source, PdfObject=PdfObject):
        ''' Some silly git put an empty object in the
            file.  Back up so the caller sees the endobj.
        '''
        source.floc = source.tokstart
        return PdfObject()

    def badtoken(self, source):
        ''' Didn't see that coming.
        '''
        source.exception('Unexpected delimiter')

    def findstream(self, obj, tok, source, PdfDict=PdfDict,
                   isinstance=isinstance, len=len):
        ''' Figure out if there is a content stream
            following an object, and return the start
            pointer to the content stream if so.

            (We can't read it yet, because we might not
            know how long it is, because Length might
            be an indirect object.)
        '''

        isdict = isinstance(obj, PdfDict)
        if not isdict or tok != 'stream':
            source.exception("Expected 'endobj'%s token",
                             isdict and " or 'stream'" or '')
        fdata = source.fdata
        startstream = source.tokstart + len(tok)

        # Skip the possible delimiters.
        possible_delimiters = ('\r', '\n', ' ')
        gotcr = gotlf = False
        while fdata[startstream] in possible_delimiters:
            if fdata[startstream] == '\r':
                gotcr = True
            if fdata[startstream] == '\n':
                gotlf = True
            startstream += 1
        if not gotlf:
            if not gotcr:
                source.warning(r'stream keyword not followed by \n')
                self.private.warned_bad_stream_start = True
            if not self.warned_bad_stream_start:
                source.warning(r"stream keyword terminated by \r without \n")
                self.private.warned_bad_stream_start = True
        return startstream

    def readstream(self, obj, startstream, source,
                   streamending='endstream endobj'.split(), int=int):
        fdata = source.fdata

        # Get a length by looking 'endstream'
        end_loc = fdata.find('endstream', startstream)
        possible_delimiters = ('\r', '\n', ' ')
        while fdata[end_loc-1] in possible_delimiters:
            end_loc -= 1
        observed_length = end_loc - startstream

        if obj.Length == None:
            length = observed_length
            source.warning('Lacking the stream length declaration, using the observed value %d.' % (observed_length))
        else:
            try:
                length = int(obj.Length)
            except:
                source.warning('Incorrect representation of stream length: %s. Use observed value %d instead.' % (obj.Length, observed_length))
                length = observed_length
            if length != observed_length:
                source.warning('Inconsistent stream length: %d declared, %d observed.' % (length, observed_length))
                length = observed_length

        source.floc = target_endstream = startstream + length
        endit = source.multiple(2)
        obj._stream = fdata[startstream:target_endstream]
        if endit == streamending:
            return

        # The length attribute does not match the distance between the
        # stream and endstream keywords.

        do_warn, self.private.warned_bad_stream_end = (self.warned_bad_stream_end,
                                               False)

        # TODO:  Extract maxstream from dictionary of object offsets
        # and use rfind instead of find.
        maxstream = len(fdata) - 20
        endstream = fdata.find('endstream', startstream, maxstream)
        source.floc = startstream
        room = endstream - startstream
        if endstream < 0:
            source.error('Could not find endstream')
            return
        if (length == room + 1 and
                fdata[startstream - 2:startstream] == '\r\n'):
            source.warning(r"stream keyword terminated by \r without \n")
            obj._stream = fdata[startstream - 1:target_endstream - 1]
            return
        source.floc = endstream
        if length > room:
            source.error('stream /Length attribute (%d) appears to '
                         'be too big (size %d) -- adjusting',
                         length, room)
            obj.stream = fdata[startstream:endstream]
            return
        if fdata[target_endstream:endstream].rstrip():
            source.error('stream /Length attribute (%d) might be '
                         'smaller than data size (%d)',
                         length, room)
            obj.stream = fdata[startstream:endstream]
            return
        endobj = fdata.find('endobj', endstream, maxstream)
        if endobj < 0:
            source.error('Could not find endobj after endstream')
            return
        if fdata[endstream:endobj].rstrip() != 'endstream':
            source.error('Unexpected data between endstream and endobj')
            return
        source.error('Illegal endstream/endobj combination')

    def loadindirect(self, key):
        result = self.indirect_objects.get(key)
        if not isinstance(result, PdfIndirect):
            return result
        source = self.source
        offset = int(self.source.obj_offsets.get(key, '0'))
        if not offset:
            #log.warning("Did not find PDF object %s" % (key,))
            return None

        # Read the object header and validate it
        objnum, gennum = key
        source.floc = offset
        objid = source.multiple(3)
        ok = len(objid) == 3
        ok = ok and objid[0].isdigit() and int(objid[0]) == objnum
        ok = ok and objid[1].isdigit() and int(objid[1]) == gennum
        ok = ok and objid[2] == 'obj'
        if not ok:
            source.floc = offset
            source.next()
            objheader = '%d %d obj' % (objnum, gennum)
            fdata = source.fdata
            offset2 = (fdata.find('\n' + objheader) + 1 or
                       fdata.find('\r' + objheader) + 1)
            if (not offset2 or
                    fdata.find(fdata[offset2 - 1] + objheader, offset2) > 0):
                source.warning("Expected indirect object '%s'" % objheader)
                return None
            source.warning("Indirect object %s found at incorrect "
                           "offset %d (expected offset %d)" %
                           (objheader, offset2, offset))
            source.floc = offset2 + len(objheader)

        # Read the object, and call special code if it starts
        # an array or dictionary
        obj = source.next()
        func = self.special.get(obj)
        if func is not None:
            obj = func(source)

        self.indirect_objects[key] = obj
        self.deferred_objects.remove(key)

        # Mark the object as indirect, and
        # add it to the list of streams if it starts a stream
        obj.indirect = key
        tok = source.next()
        if tok != 'endobj':
            self.readstream(obj, self.findstream(obj, tok, source), source)
        return obj

    def findxref(fdata):
        ''' Find the cross reference section at the end of a file
        '''
        startloc = fdata.rfind('startxref')
        if startloc < 0:
            raise PdfParseError('Did not find "startxref" at end of file')
        source = PdfTokens(fdata, startloc, False)
        tok = source.next()
        assert tok == 'startxref'  # (We just checked this...)
        tableloc = source.next_default()
        if not tableloc.isdigit():
            source.exception('Expected table location')
        if source.next_default().rstrip().lstrip('%') != 'EOF':
            source.exception('Expected %%EOF')
        return startloc, PdfTokens(fdata, int(tableloc), True)
    findxref = staticmethod(findxref)

    # Parse through the byte stream when there's no xref table available.
    def slow_parse_xref(self, source):
        setdefault = source.obj_offsets.setdefault
        add_offset = source.all_offsets.append

        def get_obj_ids(fdata):
            m = re.findall('\d+\s\d+\sobj', fdata, re.DOTALL)
            return m

        fdata = source.fdata
        obj_ids = get_obj_ids(fdata)

        xref = {}
        cur_pos = 0
        for obj_id in obj_ids:
            cur_pos = fdata.find(obj_id, cur_pos)
            #print obj_id, cur_pos
            obj_idx_id = int(obj_id.split()[0])
            obj_gen_num = int(obj_id.split()[1])
            xref[obj_idx_id] = cur_pos
            cur_pos += len(obj_id) # Done: Fixed a parsing bug here. "7 0 obj" and "17 o obj" are confusing before.

        #print xref
        for objnum,offset in xref.items():
            generation = 0
            setdefault((objnum, generation), offset)
            add_offset(offset)

    def parsexref(self, source, int=int, range=range):
        ''' Parse (one of) the cross-reference file section(s)
        '''
        fdata = source.fdata
        setdefault = source.obj_offsets.setdefault
        add_offset = source.all_offsets.append
        next = source.next
        tok = next()
        print "tok: %s" % tok
        if tok != 'xref':
            source.exception('Expected "xref" keyword')
        start = source.floc
        try:
            while 1:
                tok = next()
                if tok == 'trailer':
                    return
                startobj = int(tok)
                for objnum in range(startobj, startobj + int(next())):
                    offset = int(next())
                    generation = int(next())
                    inuse = next()
                    if inuse == 'n':
                        if offset != 0:
                            setdefault((objnum, generation), offset)
                            add_offset(offset)
                    elif inuse != 'f':
                        raise ValueError
        except:
            pass
        try:
            # Table formatted incorrectly.  See if
            # we can figure it out anyway.
            end = source.fdata.rindex('trailer', start)
            table = source.fdata[start:end].splitlines()
            for line in table:
                tokens = line.split()
                if len(tokens) == 2:
                    objnum = int(tokens[0])
                elif len(tokens) == 3:
                    offset, generation, inuse = (int(tokens[0]),
                                                 int(tokens[1]), tokens[2])
                    if offset != 0 and inuse == 'n':
                        setdefault((objnum, generation), offset)
                        add_offset(offset)
                    objnum += 1
                elif tokens:
                    log.error('Invalid line in xref table: %s' % repr(line))
                    raise ValueError
            log.warning('Badly formatted xref table')
            source.floc = end
            source.next()
        except:
            source.floc = start
            source.exception('Invalid table format')

    def readpages(self, node):
        pagename = PdfName.Page
        pagesname = PdfName.Pages
        catalogname = PdfName.Catalog
        typename = PdfName.Type
        kidname = PdfName.Kids

        # PDFs can have arbitrarily nested Pages/Page
        # dictionary structures.
        def readnode(node):
            nodetype = node[typename]
            if nodetype == pagename:
                yield node
            elif nodetype == pagesname:
                for node in node[kidname]:
                    for node in readnode(node):
                        yield node
            elif nodetype == catalogname:
                for node in readnode(node[pagesname]):
                    yield node
            else:
                log.error('Expected /Page or /Pages dictionary, got %s' %
                          repr(node))
        try:
            return list(readnode(node))
        except (AttributeError, TypeError), s:
            log.error('Invalid page tree: %s' % s)
            return []

    def __init__(self, fname=None, fdata=None, decompress=False,
                 disable_gc=True, slow_parsing=True):

        # Runs a lot faster with GC off.
        disable_gc = disable_gc and gc.isenabled()
        try:
            if disable_gc:
                gc.disable()
            if fname is not None:
                assert fdata is None
                # Allow reading preexisting streams like pyPdf
                if hasattr(fname, 'read'):
                    fdata = fname.read()
                else:
                    try:
                        f = open(fname, 'rb')
                        fdata = f.read()
                        f.close()
                    except IOError:
                        raise PdfParseError('Could not read PDF file %s' %
                                            fname)

            assert fdata is not None
            if not fdata.startswith('%PDF-'):
                startloc = fdata.find('%PDF-')
                if startloc >= 0:
                    log.warning('PDF header not at beginning of file')
                else:
                    lines = fdata.lstrip().splitlines()
                    if not lines:
                        raise PdfParseError('Empty PDF file!')
                    raise PdfParseError('Invalid PDF header: %s' %
                                        repr(lines[0]))

            endloc = fdata.rfind('%EOF')
            if endloc < 0:
                #log.error('EOF mark not found: %s' %
                #                    repr(fdata[-20:]))
                endloc = len(fdata) - 6
            endloc += 6
            junk = fdata[endloc:]
            # Done: It is not necessary to truncate the string.
            #       Some PDFs just use wrong EOF at the end to confuse parsers.
            #fdata = fdata[:endloc]
            if junk.rstrip('\00').strip():
                log.warning('Extra data at end of file')

            private = self.private
            private.indirect_objects = {}
            private.deferred_objects = set()
            private.special = {'<<': self.readdict,
                               '[': self.readarray,
                               'endobj': self.empty_obj,
                               }
            for tok in r'\ ( ) < > { } ] >> %'.split():
                self.special[tok] = self.badtoken
            if slow_parsing == True:
                startloc = 0
                source = PdfTokens(fdata, startloc, True)
                private.source = source
                # Calling next() just for complete the structure of source by adding source.current.
                source.next()
                source.all_offsets = []
                source.obj_offsets = {}
                self.slow_parse_xref(source)

                # Done: add slow parsing for multiple trailers.
                trailer_loc = fdata.find('trailer')
                newdict = None
                while trailer_loc >= 0:
                    source.floc = trailer_loc
                    assert source.next() == "trailer" # trailer
                    tok = source.next() # <<
                    if tok != '<<':
                        source.exception('Expected "<<" starting catalog')

                    # Ignored the corrupted trailer.
                    try:
                        tmpdict = self.readdict(source)
                    except:
                        pass
                    else:
                        if not newdict:
                            newdict = tmpdict
                        else:
                            newdict.update(tmpdict)
                    finally:
                        trailer_loc = fdata.find('trailer', trailer_loc+1)
                    
                if newdict is not None:
                    newdict.Prev = None
                else:
                    source.exception("No trailer.")
            else:
                startloc, source = self.findxref(fdata)
                private.source = source
                xref_table_list = []
                source.all_offsets = []
                while 1:
                    source.obj_offsets = {}
                    # Loop through all the cross-reference tables
                    self.parsexref(source)
                    tok = source.next()
                    if tok != '<<':
                        source.exception('Expected "<<" starting catalog')

                    newdict = self.readdict(source)

                    token = source.next()
                    if token != 'startxref' and not xref_table_list:
                        source.warning('Expected "startxref" at end of xref table')

                    # Loop if any previously-written tables.
                    prev = newdict.Prev
                    if prev is None:
                        break
                    if not xref_table_list:
                        newdict.Prev = None
                        original_indirect = self.indirect_objects.copy()
                        original_newdict = newdict
                    source.floc = int(prev)
                    xref_table_list.append(source.obj_offsets)
                    self.indirect_objects.clear()

                if xref_table_list:
                    for update in reversed(xref_table_list):
                        source.obj_offsets.update(update)
                    self.indirect_objects.clear()
                    self.indirect_objects.update(original_indirect)
                    newdict = original_newdict
            self.update(newdict)

            # self.read_all_indirect(source)
            private.pages = self.readpages(self.Root)
            if decompress:
                self.uncompress()

            # For compatibility with pyPdf
            private.numPages = len(self.pages)
        finally:
            if disable_gc:
                gc.enable()

            # load the trace
            fname_trace = fname + '.trace'
            if os.path.isfile(fname_trace):
                f = open(fname_trace, 'rb')
                private.active_trace = pickle.load(f)
                f.close()

    # For compatibility with pyPdf
    def getPage(self, pagenum):
        return self.pages[pagenum]

    def read_all(self):
        deferred = self.deferred_objects
        prev = set()
        while 1:
            new = deferred - prev
            if not new:
                break
            prev |= deferred
            for key in new:
                self.loadindirect(key)

    def uncompress(self):
        self.read_all()
        uncompress(self.indirect_objects.itervalues())
