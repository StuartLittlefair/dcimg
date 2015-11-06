from __future__ import absolute_import
from __future__ import print_function
import numpy as np
import sys
 
from .ContextDict import ContextDict  

# Import the xmlimporter\parser
from xml.dom import minidom

# This dictionary lists the 'simple types' that are currently supported
SimpleVarTypeDict = {
                      'DBL': 'float',
                      'I16' : 'int' ,
                      'I32': 'int',
                      'U16': 'int',                        
                      'U32': 'int',
                      'Boolean': 'bool', 
                     }

ContainerVarTypeDict = {
                      'LVData': 'container',
                      'Object' : 'container' ,
                      'Cluster': 'container',
                      'String': 'container'
                     }

# ------------------------------------------------------------
# Most important Fns for outside users - 

def parseLVDataXML_ReturnValue(XMLDomNode, VariableName, VariableType = None, ContainerNodeName = None ) :    
    ''' 
         Attempts to find + parse a LV Variable in the XML Node
         VariableType  -   currently does nothing - but could be used as an error check
         ContainerNodeName - optional - can use this to get a subset of the xml that you input    
    '''
    Local_XMLDomNode = XMLDomNode
    # If there is a Container Node name then use this to get a subset of the full node        
    if ContainerNodeName != None :
        Local_XMLDomNode = findContainerWithNameTag(Local_XMLDomNode, ContainerNodeName)
    
    # Find the variable
    Varnode = findContainerWithNameTag(Local_XMLDomNode, VariableName)
    OutputName,OutputValue,OutputType = parseLVDataXML(Varnode)
     
    return OutputValue
       

def findContainerWithNameTag(XMLDomNode,ContainerName, AllowMultipleNames = False) :
    '''
    findContainerWithNameTag: 
        
    # Finds a container with a tag name
    ie looks in XML for something like this:
        
    <SomeStructure>
        <Name>NameToFind</Name>
        <SomeOtherStuff></SomeOtherStuff>
    </SomeStructure>
    
    Returns <SomeStructure> node ie the parent of the correct name node.
    
    Complains if the name node doesn't exist - or if there are  
    
    '''       
    
    
    VarNameNodes = list()
 
    for NameNode  in XMLDomNode.getElementsByTagName("Name")   :
        if getNodeText(NameNode) == ContainerName : 
 
            VarNameNodes.append(NameNode)
    
 
    if len(VarNameNodes)== 0 :
        raise Exception("No node with this name - '{}'".format(ContainerName))
        
    if AllowMultipleNames :
        ReturnObject = list()
       
        for VarNameNode in VarNameNodes :
             ReturnObject = ReturnObject.append(VarNameNodes[0].parentNode)
        
    else:
         
        if len(VarNameNodes) > 1 :
            for VarNameNode in VarNameNodes :
               print(VarNameNode.toxml())
            raise Exception("More than one node with this name - '{}'".format(ContainerName))        
        
        ReturnObject = VarNameNodes[0].parentNode
        
        
    return ReturnObject;

#------------------------------------------------------

# Returns the text inside a XML node.
def getNodeText(node):
    rc = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            rc.append(child.data)
    return ''.join(rc)

# Prints details of the XML Tag
def printElement(LVData_XMLDomNode) :
    print("---------------------------------------") 
    print("Tag:\t",     LVData_XMLDomNode.nodeName) 
    print("Text:\t",  getNodeText(LVData_XMLDomNode).replace("\n",""))  
    print("---------------------------------------") 

def parseLVDataXML_Collection(Local_LVData_XMLDomNodes, Local_LVDatadict = None) :        
    '''
    parseLVDataXML_Collection: 
        
    Loops through XML dom hierarchy (Local_LVData_XMLDomNodes)
    NOTE - recursive 
    If Local_LVDatadict != None   
        then tries to create a nested dictionary of the variables.
    '''   
    for XMLDomNode in Local_LVData_XMLDomNodes :         # root is the ElementTree object
        LVDatadict_NewEntryName, LVDatadict_NewEntryValue, LVDatadict_NewEntryType \
                 = parseLVDataXML(XMLDomNode)
        
        if LVDatadict_NewEntryName == None \
            or LVDatadict_NewEntryValue == None\
            or Local_LVDatadict== None :
            pass
        else:
            if LVDatadict_NewEntryType  in ContainerVarTypeDict :   
                Local_LVDatadict.new_child_adopt(LVDatadict_NewEntryName, LVDatadict_NewEntryValue)
            else:       
                Local_LVDatadict[LVDatadict_NewEntryName] = LVDatadict_NewEntryValue
    
def parseLVDataXML(LVData_XMLDomNode) :        
 
    NewEntryName = None
    NewEntryValue = None

    NewEntryVariableType =  LVData_XMLDomNode.nodeName
    if not (NewEntryVariableType == '#text' and getNodeText(LVData_XMLDomNode) == '' ):        
    
        #printElement(LVData_XMLDomNode) 
        
        if False:
            pass  
        elif NewEntryVariableType  in ContainerVarTypeDict : 
            NewEntryName,NewEntryValue = _CreateNewContainerDict(LVData_XMLDomNode)
        elif NewEntryVariableType  == 'Array' :
            NewEntryName,NewEntryValue = _CreateNewSimpleArray(LVData_XMLDomNode)            
        elif NewEntryVariableType in SimpleVarTypeDict :# Number Type            
            NewEntryName, NewEntryValue, NewEntryVariableType = \
                        parseLVDataXMLSimpleVar(LVData_XMLDomNode)
        else :
            # Add a simple node to the tree
            NewEntryName = NewEntryVariableType
            NewEntryValue = getNodeText(LVData_XMLDomNode)
            
            # Check if there are children - if there are we 
            # aren't dealing with this node correctly
            LVData_XMLDomNode_HasChildren = False
            for ChildNode in  LVData_XMLDomNode.childNodes :
                if not ChildNode.nodeType ==  ChildNode.TEXT_NODE :
                    LVData_XMLDomNode_HasChildren = True        
 
            if LVData_XMLDomNode_HasChildren:
                raise Exception('%s Node Children not dealt with - missing variable' % (NewEntryVariableType ))
    return NewEntryName, NewEntryValue, NewEntryVariableType
   
def parseLVDataXMLSimpleVar(LVData_XMLDomNode) :
    NewEntryVariableType =  LVData_XMLDomNode.nodeName
    
    Local_XMLDomNode_child = LVData_XMLDomNode.getElementsByTagName("Name")[0]
    NewEntryName = getNodeText(Local_XMLDomNode_child) 
 
    Local_XMLDomNode_child = LVData_XMLDomNode.getElementsByTagName("Val")[0]
    NewEntryValue = getNodeText(Local_XMLDomNode_child) 

    if SimpleVarTypeDict[NewEntryVariableType]  == 'float' :
        NewEntryValue = float(NewEntryValue )  
    elif SimpleVarTypeDict[NewEntryVariableType]  == 'int' :  
        NewEntryValue = int(NewEntryValue ) 
    elif SimpleVarTypeDict[NewEntryVariableType]  == 'bool' :  
        NewEntryValue = bool(NewEntryValue )                     
 
    else :
        raise Exception('Variable Not Handled')  

    return NewEntryName, NewEntryValue, NewEntryVariableType   
   
    

# Creates a 'container' dictionary - for cluster type variables
def _CreateNewContainerDict(LVData_XMLDomNode) :
    
    # Find the name of the new level
    #   (want to change this from the datatype used in xml)
    New_LVDataDict_Name = LVData_XMLDomNode.nodeName
    for local_childNodes in LVData_XMLDomNode.childNodes :
        if local_childNodes.nodeName == "Name" :
            New_LVDataDict_Name = getNodeText(local_childNodes)
    
    # create new context dictionary 
    New_LVDataDict = ContextDict()
    
    # Add the type to the new dictionary
    New_LVDataDict['Type'] = LVData_XMLDomNode.nodeName
    
    # Start Parsing the new level
    parseLVDataXML_Collection(LVData_XMLDomNode.childNodes,New_LVDataDict)
     
    return New_LVDataDict_Name, New_LVDataDict 
       

# Creates and parses np array 
# ** Note will only work for 1D arrays of simple variables ATM
def _CreateNewSimpleArray( LVData_XMLDomNode) :

    # Find the name of the new level
    #   (want to change this from the datatype used in xml)
    local_NewEntryName = LVData_XMLDomNode.nodeName
    for local_childNodes in LVData_XMLDomNode.childNodes :
        if local_childNodes.nodeName == "Name" :
            local_NewEntryName = getNodeText(local_childNodes)
        if local_childNodes.nodeName == "Dimsize" :
            local_NewEntryDimsize = int(getNodeText(local_childNodes))        
    
    # create new Array
    local_NewEntryValue    = np.zeros(local_NewEntryDimsize)

    # Start Parsing the new level
    local_i = 0
    for local_XMLDomNode in LVData_XMLDomNode.childNodes :         # root is the ElementTree object

         NewEntryName, NewEntryValue, NewEntryType = parseLVDataXML(local_XMLDomNode)
                
         # if we have parsed the variable correctly then input it into the array
         if  NewEntryType in SimpleVarTypeDict :
            
            local_NewEntryValue[local_i] = NewEntryValue
            local_i = local_i+1
             


    return local_NewEntryName,local_NewEntryValue 


class LabviewXMLDataLoader():    

    def __init__(self):
        self.XMLDocNode      = None
        self.LVDataDict      = None #ContextDict()

    def loadXMLDataFile(self,filename) :        
        filename = filename
        #sys.stdout.write("Loading LabviewXML...")
        self.XMLDocNode = minidom.parse(filename)
        #sys.stdout.write("Complete\n")
        
    def loadXMLDataString(self,XMLString) : 
        #sys.stdout.write("Loading LabviewXML...")
        self.XMLDocNode = minidom.parse(XMLString)
        #sys.stdout.write("Complete\n")

    def readDataToChainDictionary(self) :          
        self.LVDataDict = ContextDict()
        #sys.stdout.write("Reading LabviewXML...")
        parseLVDataXML_Collection(  self.XMLDocNode.getElementsByTagName('LVData'), self.LVDataDict)
        #sys.stdout.write("Complete\n")
                


if __name__ == '__main__':
    import sys
    filename        = sys.argv[1]
    LabviewXMLData  = LabviewXMLDataLoader()
    LabviewXMLData.loadXMLDataFile(filename)
    
    
    # Reads the data into a nested dictionary
    # - probably not so useful in practice - since the XML dom has been written 
    #   already to do searches etc. 
    # Might be useful if you don't know what the structure is in advance
    LabviewXMLData.readDataToChainDictionary() 
    
    print("\n\n DATA:")
    print(str(LabviewXMLData.LVDataDict)) 
    """
    # Directly accesing a variable using the nested dictionary
   # print LabviewXMLData.LVDataDict['LVData']['PulsedMeasurement out']['PulsedMeasurement_v2.lvclass']['PulsedMeasurment Inputs']['HighTime(Arrayx4) (s)']  
    
    #print LabviewXMLData.LVDataDict.find_key_refs('StepSize(um)', True)       
     
    # Using a find function in the nested dictionaries to find a value (needs to be unique)
    print(LabviewXMLData.LVDataDict.find_key_value('StepSize(um)', True))   


    # Using a find function in the nested dictionaries to find a list of references (not unique)
    print(LabviewXMLData.LVDataDict.find_key_refs('HighTime(Arrayx4) (s)', True))

    # Finding the path to a variable.
    print(LabviewXMLData.LVDataDict.find_key_refs('HighTime(Arrayx4) (s)', True)[0].return_path_to_root())


    # Using a find function in the nested dictionaries to find a value
    print(LabviewXMLData.LVDataDict['LVData']['PulsedMeasurement out']['PulsedMeasurement_v2.lvclass']['PulsedMeasurment Inputs']['AOM Pulse Parameters']['HighTime(Arrayx4) (s)'])
 
 
    
    # Using the XML dom to do the same
    print(parseLVDataXML_ReturnValue(\
                            LabviewXMLData.XMLDocNode,'HighTime(Arrayx4) (s)','I32', 'AOM Pulse Parameters'))
    """