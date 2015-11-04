import arcpy
import os

# module for listing datasets


def list_datasets(location,**kwargs):
    ''' (str[,datatype = str[,type = str][,exclusion = str]) -> list

    Takes an input string of the directory (or workspace)
    containing the datasets and recursively returns all filepaths into a list.
    Optional datatype,subtype and exlusion args can be set to limit the results.
    If you want to exclude a folder, set the 'exclusion' parameter to the directory name (or list of names).
    You may also set 'datatype' and 'type' parameters according to the arcpy.da.Walk syntax (http://resources.arcgis.com/EN/HELP/MAIN/10.2/index.html#//018w00000023000000")
    
    

    >>> get_features("C:/workspace",datatype = "FeatureClass",type = "Polygon",exclusions = "Projected")
    >>> [list of all polygon feature classes in 'C:/workspace', excluding all those in a subdirectory named "Projected"]

    '''
    result = []
    dtyp = None
    typ = None
    excl = False 
    
    if kwargs:
        for key,value in kwargs.items():
            if key == "datatype":
                dtyp = value
            elif key == "type":
                typ = value
            elif key == "exclusion":
                excl = value
            else:
                arcpy.AddMessage("Invalid optional input parameters. Optional parameters are: datatype = 'str', type = 'str', exclusion = 'str'")

    if excl:
        for dirpath,dirnames,files in arcpy.da.Walk(location,datatype = dtyp,type = typ):
            if excl in dirnames:
                dirnames.remove(excl)
            for filename in files:
                result.append(os.path.join(dirpath,filename))
    else:
        for dirpath,dirnames,files in arcpy.da.Walk(location,datatype = dtyp,type = typ):
            for filename in files:
                result.append(os.path.join(dirpath,filename))
    return result
        

