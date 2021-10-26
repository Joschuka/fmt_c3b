# Dragon Quest Aces
# Noesis script by Dave, Joschka 2021

from inc_noesis import *

#Version 0.1

# =================================================================
# Plugin options
# =================================================================

bLoadAnims = True #if set to True, will ask for an animation folder and load every file there

def registerNoesisTypes():
    handle = noesis.register("Dragon Quest Aces",".c3b")
    noesis.setHandlerTypeCheck(handle, bcCheckType)
    noesis.setHandlerLoadModel(handle, bcLoadModel)
    return 1

def ValidateInputDirectory(inVal):
	if os.path.isdir(inVal) is not True:
		return "'" + inVal + "' is not a valid directory."
	return None

# Check file type

def bcCheckType(data):
    bs = NoeBitStream(data)
    file_id = bs.readUInt()

    if file_id != 0x00423343:
        return 0
    else:
        return 1

def findShapeName(bs):
    indexFlag = b'\x73\x68\x61\x70\x65'
    a=True
    while a:
        checkPoint = bs.tell()
        if bs.tell() > bs.getSize()-10:
            return 0
        temp = bs.readBytes(0x5)
        if temp == indexFlag:
            bs.seek(checkPoint-4)
            a = False
        else :
            bs.seek(checkPoint+1)
    return 1


def LoadAnim(name, data, jointList, nameToIndex):
    bs = NoeBitStream(data)
    keyFramedBoneList = []
    bs.seek(0x06)
    header_entries = bs.readUInt()
    animOffs = -1
    for a in range(header_entries):
        entry_name = ReadText(bs)

        if "animation" in entry_name:
            bs.readUInt()
            animOffs = bs.readUInt()
        else:
            bs.readBytes(8)
    if animOffs < 0:
        print("No anim file")
        return [False, None]
    bs.seek(animOffs)
    ReadText(bs)
    duration = bs.readFloat()
    jCount = bs.readUInt()
    for _ in range(jCount):
        jointName = ReadText(bs)
        kfCount = bs.readUInt()
        rotNoeKeyFramedValues = []
        posNoeKeyFramedValues = []
        scaleNoeKeyFramedValues = []
        for __ in range(kfCount):
            timing = bs.readFloat()
            semantic = bs.readByte()
            rotation = None
            position = None
            scale = None
            if semantic == 0x7:
                rotation = bs.read('4f')
                scale = bs.read('3f')
                position = bs.read('3f')
            elif semantic == 0x6:
                scale = bs.read('3f')
                position = bs.read('3f')
            elif semantic == 0x5:
                rotation = bs.read('4f')
                position = bs.read('3f')
            elif semantic == 0x4:
                position = bs.read('3f')
            elif semantic == 0x3:
                rotation = bs.read('4f')
                scale = bs.read('3f')
            elif semantic == 0x2:
                scale = bs.read('3f')
            elif semantic == 0x1:
                rotation = bs.read('4f')
            else:
                print("UNKNOWN SEMANTIC at : ", bs.tell(),semantic)
                return
            if rotation is not None:
                rotNoeKeyFramedValues.append(NoeKeyFramedValue(timing,NoeQuat(rotation).transpose()))
            if scale is not None:
                scaleNoeKeyFramedValues.append(NoeKeyFramedValue(timing,NoeVec3(scale)))
            if position is not None:
                posNoeKeyFramedValues.append(NoeKeyFramedValue(timing,NoeVec3(position)))
        if jointName in nameToIndex:
            jointID = nameToIndex[jointName]
            actionBone = NoeKeyFramedBone(jointID)
            actionBone.setRotation(rotNoeKeyFramedValues, noesis.NOEKF_ROTATION_QUATERNION_4)
            actionBone.setTranslation(posNoeKeyFramedValues, noesis.NOEKF_TRANSLATION_VECTOR_3)
            actionBone.setScale(scaleNoeKeyFramedValues, noesis.NOEKF_SCALE_VECTOR_3)
            keyFramedBoneList.append(actionBone)
        else:
            print("missing bone " + jointName)
    anim = NoeKeyFramedAnim(name, jointList, keyFramedBoneList, 30)
    return anim	
    

# Read the model data

def bcLoadModel(data, mdlList):
    bs = NoeBitStream(data)
    ctx = rapi.rpgCreateContext()
    global currentChild
    currentChild = [0]

    bs.seek(0x06)
    header_entries = bs.readUInt()

    mat_table = -1
    node_table = -1
    mesh_count = -1
    

    for a in range(header_entries):
        entry_name = ReadText(bs)

        if "animation" in entry_name:
            bs.readBytes(8)

        if "material" in entry_name:
            bs.readUInt()
            mat_table = bs.readUInt()

        if "node" in entry_name:
            bs.readUInt()
            node_table = bs.readUInt()

        if "mesh" in entry_name:
            bs.readBytes(8)
    mesh_count = bs.readUInt()

    if mesh_count == -1:
        print("This C3B file doesn't contain any meshes.")
        return 0


    mesh_start = bs.tell()

    mat_list, tex_list = ReadTextures(bs, mat_table)
    
    jointList, bMaps, nameToIndex = ReadJoints(bs, node_table)
    jointList = rapi.multiplyBones(jointList)
    
    animList = []
    animPaths = []
    if bLoadAnims:
        animDir = noesis.userPrompt(noesis.NOEUSERVAL_FOLDERPATH, "Open Folder", "Select the folder to get the animations from", noesis.getSelectedDirectory(), ValidateInputDirectory)
        if animDir is not None:
            for root, dirs, files in os.walk(animDir):
                for fileName in files:
                    lowerName = fileName.lower()
                    if lowerName.endswith(".c3b"):
                        fullPath = os.path.join(root, fileName)
                        animPaths.append(fullPath)
    
    for animPath in animPaths:
        with open(animPath, "rb") as animStream:
            animName = os.path.basename(animPath)[:-4]
            animList.append(LoadAnim(animName, animStream.read(), jointList, nameToIndex))	

    for a in range(mesh_count):
        mesh_start = DrawMesh(bs, mesh_start,mat_list, bMaps)

    mdl = rapi.rpgConstructModel()
    mdl.setModelMaterials(NoeModelMaterials(tex_list, mat_list))
    mdl.setBones(jointList)
    mdl.setAnims(animList)
    mdlList.append(mdl)

    return 1

def ProcessPList(childrenCounts, pList, currentParent = 0):
    for i in range(1,childrenCounts[currentParent]+1):
        currentChild[0] += 1
        if currentChild[0] <len(pList):
            pList[currentChild[0]] = currentParent
            if childrenCounts[currentChild[0]]:
                ProcessPList(childrenCounts, pList, currentChild[0])
                
def ReadJoints(bs, node_table):
    bs.seek(node_table)
    jointList = []
    childrenCounts = []
    mats = []
    names = []
    bMaps = {}
    nameToIndex = {}
    
    bs.readUInt()
    a = 0
    while not a:
        name = ReadText(bs)
        bs.readByte()
        mat = NoeMat44.fromBytes(bs.readBytes(64)).toMat43()
        a = bs.readUInt()
        cCount = bs.readUInt()
        if not a :
            nameToIndex[name] = len(names)
            names.append(name)
            mats.append(mat)
            childrenCounts.append(cCount)			
    
    pList = [-1 for name in names]
    ProcessPList(childrenCounts, pList)
    for i,(name, mat, p) in enumerate(zip(names, mats, pList)):
        jointList.append(NoeBone(i,name, mat,None, p))
        
    #bone maps
    while findShapeName(bs):
        bMap = []		
        name = ReadText(bs)
        ReadText(bs)
        entryCount = bs.readUInt()
        for i in range(entryCount):
            bMap.append(nameToIndex[ReadText(bs)])
            bs.readBytes(64)
        bMaps[name] = bMap
    
    return [jointList, bMaps, nameToIndex]

def ReadText(bs):
    txt_len = bs.readUInt()
    text1 = bs.readBytes(txt_len).decode("utf-8")
    return text1


# Draw mesh

def DrawMesh(bs, offset,mat_list, bMaps):
    bs.seek(offset)
    vert_entries = bs.readUInt()
    position = 0

    pos_offset = -1
    normal_offset = -1
    color_offset = -1
    uv_offset = -1
    uv2_offset = -1
    weight_offset = -1
    index_offset = -1

# Vertex stride varies, so have to calculate it from the elements listed

    for b in range(vert_entries):
        items = bs.readUInt()					# number of components for this vertex type
        entry_type = ReadText(bs)					# number format - usually "GL_FLOAT"
        entry_name = ReadText(bs)					# Vertex entry type

        if entry_name == "VERTEX_ATTRIB_POSITION":
            pos_offset = position

        if entry_name == "VERTEX_ATTRIB_NORMAL":
            normal_offset = position

        if entry_name == "VERTEX_ATTRIB_COLOR":
            color_offset = position

        if entry_name == "VERTEX_ATTRIB_TEX_COORD":
            uv_offset = position

        if entry_name == "VERTEX_ATTRIB_TEX_COORD1":
            uv2_offset = position

        if entry_name == "VERTEX_ATTRIB_BLEND_WEIGHT":
            weight_offset = position

        if entry_name == "VERTEX_ATTRIB_BLEND_INDEX":
            index_offset = position

        position += (items * 4)

    vert_stride = position
    vertices = bs.readBytes(bs.readUInt() * 4)

    rapi.rpgBindPositionBufferOfs(vertices, noesis.RPGEODATA_FLOAT, vert_stride, pos_offset)
    rapi.rpgBindNormalBufferOfs(vertices, noesis.RPGEODATA_FLOAT, vert_stride, normal_offset)
    rapi.rpgBindUV1BufferOfs(vertices, noesis.RPGEODATA_FLOAT, vert_stride, uv_offset)
    if index_offset >=0:
        rapi.rpgBindBoneIndexBufferOfs(vertices, noesis.RPGEODATA_FLOAT, vert_stride, index_offset, 4)
        rapi.rpgBindBoneWeightBufferOfs(vertices, noesis.RPGEODATA_FLOAT, vert_stride, weight_offset, 4)
    submesh_count = bs.readUInt()

    for m in range(submesh_count):
        mesh_name = ReadText(bs)
        face_count = bs.readUInt()
        faces = bs.readBytes(face_count * 2)
        bs.readBytes(24)

        rapi.rpgSetName(mesh_name)
        if bMaps[mesh_name]:
            rapi.rpgSetBoneMap(bMaps[mesh_name])
        rapi.rpgSetMaterial(mat_list[0].name)
        rapi.rpgCommitTriangles(faces, noesis.RPGEODATA_USHORT, face_count, noesis.RPGEO_TRIANGLE)

    next_mesh = bs.tell()
    rapi.processCommands("-flipuv")
    return next_mesh



def ReadTextures(bs, mat_table):
    mat_list = []
    tex_list = []

    bs.seek(mat_table)
    mat_count = bs.readUInt()

    for m in range(mat_count):
        mat_name = ReadText(bs)
        bs.readBytes(0x38)
        sub_count = bs.readUInt()

        material = NoeMaterial(mat_name, "")

        for s in range(sub_count):
            sub_text = ReadText(bs)
            filename = ReadText(bs)
            fullName = rapi.getDirForFilePath(rapi.getInputName()) + os.sep + filename
            bs.readBytes(16)
            tex_type = ReadText(bs)
            misc1 = ReadText(bs)
            misc2 = ReadText(bs)
            texture = rapi.loadTexByHandler(rapi.loadIntoByteArray(fullName),".png")
            texture.name = filename[:-3]+".dds"
            tex_list.append(texture)
            if tex_type == "DIFFUSE":
                material.setTexture(texture.name)
                material.defaultBlend = False

            if tex_type == "TRANSPARENCY":
                material.setOpacityTexture(texture.name)

        mat_list.append(material)

    return [mat_list,tex_list]

