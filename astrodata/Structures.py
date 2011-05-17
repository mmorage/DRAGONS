# The Structure system includes two main classes
import os, sys, re
import AstroData

from ConfigSpace import config_walk

# some common defines mainly for Structure Definition Modules
# these are standard strings, these variable save typing quotes

arrayBy = "arrayBy"
optional = "optional"
retain = "retain"
structure = "structure"

class StructureExcept:
    """ This is the general exception the classes and functions in the
    Structures.py module raise.
    """
    def __init__(self, msg="Exception Raised in Structure Projection system"):
        """This constructor accepts a string C{msg} argument
        which will be printed out by the default exception 
        handling system, or which is otherwise available to whatever code
        does catch the exception raised.
        @param msg: a string description about why this exception was thrown
        @type msg: string
        """  
        self.message = msg
    def __str__(self):
        """This string operator allows the default exception handling to
        print the message associated with this exception.
        @returns: string representation of this exception, the self.message member
        @rtype: string"""
        return self.message
    
class ProjectionExcept(StructureExcept):
    """ This exception is raised to communicate (potentially) fatal errors
    when applying structure to an AstroData instance. For example, when 
    a structure is applying a member already present in the AstroData
    instance (due to another projection or any other reason).
    
    @note: By "projection" in this context I am talking about the members
    defined in the structure description which are then added to the AstroData
    instance at run time.  Multiple structure can apply to a single set of data
    and probably will, but they must not project the same members at the same level.
    """
    pass

class Part(object):
    """ The Part class is an element of the Stucture and ExtID classes
    pattern seeking system.  The Structure classes can be thought of etching
    the structure found in a hierarchy of Part instances.  A Structure
    and ExtID hierarchy is a template, and the Part Hierarchy is the 
    material instance of the structure relationships. The Part hierarchy 
    refers to Structure instances. To project the structure we recurse 
    the Part instance hierarchy.
    """
    #: This is the name this part will have as a member variable of the
    #: AstroData instance 
    #: into which it is projected.
    struct_name = None
    #: The instance of the Structure or ExtID instance at this point in 
    #: the hierarchy.
    struct_inst = None   
    #: The string name of the struct_class at this point in the structure.
    struct_class = None
    #: A string name of the header variable use to array this part.
    array_by = None
    #: A boolean indicating if this part is required or not
    required = True
    #: Either None or a dictionary of header requirements inherited from 
    #: up the hierarchy
    other_reqs = None # requirements given by superstructure
    
    def __init__(self, structClass = None, arrayBy = None, 
                    name=None, otherReqs={}, required=True):
        """Constructor for Part class.
        @param structClass: Class name to instantiate for this part, a string which 
        must be a valid python class name.
        @type structClass: string
        @param arrayBy: Header Name this is being "arrayed by" (e.g. "EXTVER")
        @type arrayBy: string
        @param name: The member name this part will have in the AstroData 
        instance to which this structure is projected.
        @type name: string 
        @param otherReqs: A dictionary of requirements passed down the
        parts, ultimately to the ExtID instances, imposed by higher parts
        of the hierarchy.
        @type otherReqs: dictionary
        @param required: Specifies if this part is required or can be left off if
        unmatched
        @type required: bool
        """
        # print "S24: structClass is %s" % structClass
        if otherReqs == None:
            otherReqs = {}
            
        if isinstance(structClass, Part):
            raise StructureExcept("Can't use Part to initialize part... doesn't work like that")
        else:
            self.required=required
            self.struct_class = structClass
            if structClass != None:
                self.struct_inst = instantiate_struct(structClass)
                self.struct_inst.other_reqs = otherReqs.copy()
            self.array_by = arrayBy
            self.struct_name = name
            self.other_reqs = otherReqs.copy()
            
class PartList(Part, list):
    """This class is for a part that is an array.
    """
    pass
        
class Structure(object):
    """ The Structure Class encapsulates the nodes of hierarchy
    in the data structures we want to project.  This class manages
    the structure discovery process. Structures are defined as a 
    tree of Structure Instances which terminate in L{ExtID} instances.
    """
    cdebug = False # flag for printing debug messages

    parts = None
    partInsts = None
    otherReqs = None
    def find(self, dataset):
        """
        This function attempts to find the structure given in the dataset given.
        @param dataset: the data in which to seek the structure defined in
        this structure instance (based also on the structure of the structure
        members).
        @type dataset: AstroData instance
        """
        if (self.otherReqs == None):
            self.otherReqs = {}
        partkeys = self.parts.keys()

        self.partInsts = []
        
        for partkey in partkeys:
            partattr = self.parts[partkey]
            if type(partattr) == str:
                # string part definitions are just the StructClass name
                structClass = partattr
                arrayBy = None
                required = True
            elif type(partattr) == dict:
                # if the partattr is a dict, it is a dict of attributes for that node
                # of the structure.
                try:
                    structClass = partattr["structure"]
                except KeyError:
                    raise StructureExcept("Structure Part Does not Define Structure")
                try:               
                    arrayBy = partattr["arrayBy"]
                except KeyError:
                    arrayBy = None
                try:
                    # specifies if part is optional, default: False (required == True)
                    # NOTE: "optional" parm relates to "required"
                    required = not partattr["optional"]
                except KeyError:
                    required = True
            
            newPart = None
            if arrayBy != None:
                # then this part is an array
                # create associateByList
                associateList = get_concrete_array_by_values(dataset, array_by = arrayBy, reqs = self.otherReqs)
                # for each concrete association
                newPartAry = PartList(None, 
                                arrayBy = arrayBy, 
                                name=partkey, 
                                otherReqs = self.otherReqs, 
                                required=required)
                for associateVal in associateList:
                    # define other_reqs to pass in, the one we got as an arg
                    # plus the arrayBy:associateVal addition
                    addReqs = self.otherReqs.copy()
                    addReqs.update({arrayBy:associateVal})
                    #  instantiate part with reqs (which it saves)
                    newPart = Part(structClass, 
                                arrayBy = arrayBy, 
                                name=partkey, 
                                otherReqs = addReqs, 
                                required=required)
                    newPartAry.append(newPart)
                    
                self.partInsts.append(newPartAry)
            else:
                # instantiate singlular part
                newPart = Part(structClass, 
                            arrayBy = arrayBy, 
                            name=partkey, 
                            otherReqs = self.otherReqs, 
                            required=required)
                if newPart != None:
                    self.partInsts.append(newPart)
        
        # do the find... arrays of structure/ExtIDs should exist
        # and other_reqs should have been communicated to the leaves in the 
        # instantiation process.
        for part in self.partInsts:
            if isinstance(part,list):
                for subpart in part:
                    # @@TODO: make this a function call in common with block below
                    bFound = subpart.struct_inst.find(dataset)
                    if bFound == False:
                        if part.required == False:
                            part.struct_inst = None
                        else:
                            errstr = str(subpart.other_reqs)
                            raise StructureExcept("Temporary Exception... failure when required == True\n" + errstr)
                            
                            return False
            else:
                bFound = part.struct_inst.find(dataset)
                if bFound == False:
                    if part.required == False:
                        part.struct_inst = None
                    else:
                        errstr = str(part.other_reqs)
                        raise StructureExcept("Temporary Exception... failure when required == True"+ errstr)
                        return False
        
        return True
    
    def project(self, dataset):
        """
        This function will project a structure onto a given AstrData object,
        that is, it will add the correct members to the AstroData instance.
        In short, this function attaches an AstroData instance, or, 
        for array members, a list of AstroData instances, as a member of the
        given dataset which contains the extensions in that section of the dataset.
        
        NOTE: the structure should have been previously "found" 
        (e.g. via 'structureInstance.find(dataset)').
        @param dataset: the AstroData instance to which to apply the structure members
        @type dataset: AstroData instance
        """
        # @@TODO: check this dataset was the one used for the same find (store id in part array somewhere)
        for part in self.partInsts:
            if isinstance(part,list):
                newmem = []
                for subpart in part:
                    exts = subpart.struct_inst.get_extensions()
                    newds = AstroData.AstroData(dataset, extInsts = exts)
                    newmem.append(newds)
                    subpart.struct_inst.project(newds)                    
                newmemstr = "dataset.%s" % part.struct_name
                # check if this is already projected... note, we WANT an attributeerror
                # here to ensure the attribute is not already projected.
                # NOTE: this may not be the behavior we want eventually, but right now
                # this will help us avoid conflicts.
                try:
                    testattr = eval(newmemstr)
                    raise ProjectionExcept('Projection Conflict, member "%s" already exists' % part.struct_name)
                except AttributeError:
                    pass
                
                projectstr = "%s = newmem" % newmemstr
                exec(projectstr)
                if (self.cdebug):
                    print "projectstr = '%s' (dataset=%s)" % (projectstr, str(dataset))
            elif isinstance(part, Part):
                if (part.struct_inst != None):
                    exts = part.struct_inst.get_extensions()
                    newds = AstroData.AstroData(dataset, extInsts = exts)
                else:
                    newds = None
                newmemstr = "dataset.%s" % part.struct_name
                try:
                    testattr = eval(newmemstr)
                    raise ProjectionExcept('Projection Conflict, member "%s" already exists' % part.struct_name)
                except AttributeError:
                    pass
                projectstr = "%s = newds" % newmemstr
                if (self.cdebug):
                    print "projectstr = '%s' (dataset=%s)" % (projectstr, str(dataset))
                exec(projectstr)
                if part.struct_inst != None:
                    part.struct_inst.project(newds)
            else:
                # only options... how did a non-Part class get here?
                raise StructureExcept("Non Part Class found in part array - fatal flaw")
    def get_extensions(self):
        retary = []
        for part in self.partInsts:
            if part.struct_inst != None:
                exts = part.struct_inst.get_extensions()
                if exts != None:
                    retary += exts
        return retary

    def printout(self,dataset,prefix = "", nest = 0):
        indent = ""
        for i in range(0,nest):
            indent += "   "
            
        for part in self.partInsts:
            if isinstance(part,list):
                i = 0
                for subpart in part:
                    i += 1
                    if (subpart.struct_inst != None):
                        fix = "%s[%d]" % (subpart.struct_name, i)
                        print "%sGD.%s%s" % (indent,prefix,fix)
                        subpart.struct_inst.printout(dataset, prefix = prefix+fix+".", nest = nest+1)
            else:
                if (part.struct_inst != None):
                    print "%sGD.%s%s" % (indent, prefix, part.struct_name)
                    part.struct_inst.printout(dataset, prefix = prefix+part.struct_name+".", nest = nest+1)
            
            
class ExtID(object):
    """
    The ExtID class acts as the leaf node in Structure instance hierarchies
    which capture the over all structure of the data. It's role as leaf node
    is to recognize specific extensions being looked for. An ExtID class will 
    have some extension requirements (i.e. on the extension header) it understand
    innately (e.g. "EXTNAME" should be "SCI") but will have some of the
    recognition requirements given to it (e.g. told to find "EXTVER" == 2)
    as a result of requirements from higher in the structure tree.
    @ivar head_reqs: a dictionary which contains extension header keys as keys,
    and identifying values within the map values.
    @type head_reqs: dictionary
    """
    head_reqs = None
    extension = None # Note: this is (should be) a single extension 
                     # .. AstroData instance
    cdebug = False
    other_reqs = None
    def printout(self, dataset, prefix = "", nest=0):
        indent = ""
        for i in range(0,nest):
            indent += "   "
            
        if self.extension!=None:
            print "%sExtID: (%s,%d) %s" % (indent, 
                                           self.extension.header["EXTNAME"],
                                           self.extension.header["EXTVER"],
                                           str(self.extension))
        else:
            print "%sExtID: None" % (indent)
    def project(self, dataset):
        """
        The Structure Class actually manage projection, as it's a recursive
        call ExtID only needs to terminate this call (by not recursing further
        as it is always a leaf node).  This function therefore currently has
        C{pass} as its body.
        """
        # I don't do anything, my container, a Structure instance does this
        pass
    
    def get_extensions(self):
        """
        This function returns the extension identified by this node. 
        C{get_extensions()} Should be called only after "find" has been
        called, and is part of the structure projection process.
        @return: the extension previously found in call to C{find(..)}
        @rtype: an HDU instance
        """
        if self.extension!= None:
            return [self.extension.hdulist[1]]
        else:
            return None
    def find(self, dataset):
        """
        This function will try to find the extension matching
        its requirements in the given dataset.
        @param dataset: The data set in which to seek the extension
        this ExtID seeks.
        @type dataset: AstroData instance
        """
        allReqs = self.head_reqs.copy()
        if self.other_reqs != None:
            allReqs.update(self.other_reqs)
            
        if (self.cdebug):
            print "ExtID: finding:\n\t%s" % str(allReqs)
        for ext in dataset:
            bMatch = True # falsified below
            for hkey in allReqs.keys():
                try:
                    if ext.header[hkey] != allReqs[hkey]:
                        bMatch = False
                        break
                except KeyError:
                    bMatch = False
                    break
            if bMatch == True:
                self.extension = ext
                return True
            # else we try again via the loops
        return False
        

#functions


def apply_structure_by_type(dataset):
    """ Apply all structures to dataset based on which types apply to
    the given dataset
    @param dataset: dataset to apply structure to
    @type dataset: AstroData instance
    @return: The number of structures applied
    @rtype: int
    """
    types = dataset.get_types()
    applied = 0
    for typ in types:
        # see if there is a structure
        try:
            structstr = centralStructureIndex[typ]
        except KeyError:
            # no structure
            continue
        
        if structstr != None:
            applied += 1
            structObj = instantiate_struct(structstr)
            #@@TODO: what if this is false... not handling at all
            structObj.find(dataset)
            structObj.printout(dataset)
            structObj.project(dataset)
            try:
                ls = dataset.structures
                if type(ls) != list:
                    ls = []
                    dataset.structures = ls
            except AttributeError:
                dataset.structures = []
                
            dataset.structures.append(structObj)
    
    return applied

def instantiate_struct(structstr):
    modname = structstr.split(".")[0]
    exec "import " + modname
    return eval (structstr)

def get_concrete_array_by_values(dataset, array_by, reqs = None):
    if array_by == None:
        raise StructureExcept("Structure.py: cannot get concrete values; array_by == None")
    
    retlist = []
    
    # is going through the whole list of extensions sensible?
    for ext in dataset.hdulist[1:]:
        eheader = ext.header.ascardlist()
        passedReqs = True # falsified  if need by by guantlet below below
        if reqs != None:
            for reqkey in reqs.keys():
                try:
                    if eheader[reqkey].value != reqs[reqkey]:
                        # one falure is one too many, this is not an extension we are 
                        # looking at in the callers part of the structure
                        passedReqs = False
                        break
                except KeyError:
                    # means match failed, exists in reqs but not eheader
                    passedReqs = False
                    break
        
        if (passedReqs == True):
            # might mean there were no extra reqs...
            # ncv == New Concrete Value (to add to retlist)
            try:
                ncv = eheader[array_by]
                if ncv.value not in retlist:
                    retlist.append(ncv.value)
            except KeyError:
                # just means this extension doesn't have a concrete value to contribute
                # which also means it won't be found in this part of the structure
                # which obviously means it has not passed... MUST HAVE whatever
                # the array_by key is...
                pass
            
    return retlist

# CODE THAT RUNS ON IMPORT
# THIS MODULE ACTS AS A SINGLETON FOR STRUCTURE FEATURES

# NOTE: The issue of a central service for structure implies a need for
# a singleton as with the ClassificationLibrary and the Descriptors.py module.
# I have adopted the module-as-singleton approach for Structures as it does
# not involve the message try-instantiate-except block.  I'm checking into
# possible complications but it seems acceptable python.

#: structureIndexREMask used to identify which files by filename
#: are those with tables relating type names to structure types
structureIndexREMask = r"structIndex\.(?P<modname>.*?)\.py$"
    
if (True): # was firstrun logic... python interpreter makes sure this module only runs once already
    # this module operates like a singleton
    
    centralStructureIndex = {}
    
    # WALK the directory structure
    # add each directory to the sytem path (from which import can be done)
    # and exec the structureIndex.***.py files
    # These indexes are meant to append it to the centralDescriptorIndex
    
    for root, dirn, files in config_walk("structures"):
        sys.path.append(root)
        for sfilename in files:
            if (re.match(structureIndexREMask, sfilename)):
                fullpath = os.path.join(root, sfilename)
                siFile = open(fullpath)
                exec siFile
                siFile.close()
                # file must declare structureIndex = {...}, keys are types, 
                # values are string names of structure classes that can
                # be instantiated when needed (should refer to modules
                # and classes in structures subdirectory, all of which is
                # in the import path.
                
                # note: make sure one index does not stomp another
                # Means misconfigured structureIndex.
                
                for key in structureIndex.keys():
                    if centralStructureIndex.has_key(key):
                        # @@log
                        msg = "Scructure Index CONFLICT\n"
                        msg += "... structure for type %s\n" % key
                        msg += "redefined in\n" 
                        msg += "... %s\n" % fullpath
                        msg += "... was already set to %s\n" %centralStructureIndex[key]
                        msg += "... this is a fatal error"
                        raise StructureExcept(msg)
                        
                centralStructureIndex.update(structureIndex)
