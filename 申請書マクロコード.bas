
Public Sub ExportConfigJSON()
    On Error GoTo ErrHandler
    
    ' Sheet name variables
    Dim SH_LINE As String: SH_LINE = ChrW(25237) & ChrW(20837) & ChrW(20516) & ChrW(23450) & ChrW(32681) & "(" & ChrW(32218) & ChrW(35373) & ChrW(20633) & ")"
    Dim SH_POINT As String: SH_POINT = ChrW(25237) & ChrW(20837) & ChrW(20516) & ChrW(23450) & ChrW(32681) & "(" & ChrW(28857) & ChrW(35373) & ChrW(20633) & ")"
    Dim SH_POLE As String: SH_POLE = ChrW(25237) & ChrW(20837) & ChrW(20516) & ChrW(23450) & ChrW(32681) & "(" & ChrW(38651) & ChrW(26609) & ChrW(39006) & ")"
    Dim SH_SETTINGS As String: SH_SETTINGS = "JSON" & ChrW(35373) & ChrW(23450)
    
    Dim wsMain As Worksheet: Set wsMain = ActiveSheet
    Dim shName As String: shName = wsMain.Name
    
    If shName <> SH_LINE And shName <> SH_POINT And shName <> SH_POLE Then
        MsgBox ChrW(25237) & ChrW(20837) & ChrW(20516) & ChrW(23450) & ChrW(32681) & ChrW(12471) & ChrW(12540) & ChrW(12488) & ChrW(12363) & ChrW(12425) & ChrW(23455) & ChrW(34892) & ChrW(12375) & ChrW(12390) & ChrW(12367) & ChrW(12384) & ChrW(12373) & ChrW(12356) & ChrW(12290), vbExclamation, ChrW(12456) & ChrW(12521) & ChrW(12540)
        Exit Sub
    End If
    
    ' Read config path from B5 (supports both folder and file path)
    Dim rawPath As String: rawPath = Trim(CStr(wsMain.Range("B5").Value))
    If rawPath = "" Then
        MsgBox "Config" & ChrW(12501) & ChrW(12449) & ChrW(12452) & ChrW(12523) & ChrW(12497) & ChrW(12473) & ChrW(12364) & ChrW(26410) & ChrW(20837) & ChrW(21147) & ChrW(12391) & ChrW(12377) & ChrW(12290), vbExclamation, ChrW(20837) & ChrW(21147) & ChrW(12456) & ChrW(12521) & ChrW(12540)
        Exit Sub
    End If
    
    Dim fp As String
    If LCase(Right(rawPath, 5)) = ".json" Then
        fp = rawPath
    Else
        If Right(rawPath, 1) <> "\" Then rawPath = rawPath & "\"
        fp = rawPath & "config.json"
    End If
    
    ' Read basic info
    Dim pName As String: pName = Trim(CStr(wsMain.Range("B3").Value))
    Dim fType As String: fType = Trim(CStr(wsMain.Range("B4").Value))
    If pName = "" Or fType = "" Then
        MsgBox ChrW(20107) & ChrW(26989) & ChrW(32773) & ChrW(21517) & ChrW(12414) & ChrW(12383) & ChrW(12399) & ChrW(35373) & ChrW(20633) & ChrW(12479) & ChrW(12452) & ChrW(12503) & ChrW(12364) & ChrW(26410) & ChrW(20837) & ChrW(21147) & ChrW(12391) & ChrW(12377) & ChrW(12290), vbExclamation, ChrW(20837) & ChrW(21147) & ChrW(12456) & ChrW(12521) & ChrW(12540)
        Exit Sub
    End If
    Dim mName As String: mName = pName & fType
    
    ' Resolve key mapping sheet based on active sheet
    Dim wsMap As Worksheet
    Dim kmLine As String: kmLine = ChrW(12461) & ChrW(12540) & ChrW(12510) & ChrW(12483) & ChrW(12500) & ChrW(12531) & ChrW(12464) & "(" & ChrW(32218) & ChrW(35373) & ChrW(20633) & ")"
    Dim kmPoint As String: kmPoint = ChrW(12461) & ChrW(12540) & ChrW(12510) & ChrW(12483) & ChrW(12500) & ChrW(12531) & ChrW(12464) & "(" & ChrW(28857) & ChrW(35373) & ChrW(20633) & ")"
    Dim kmPole As String: kmPole = ChrW(12461) & ChrW(12540) & ChrW(12510) & ChrW(12483) & ChrW(12500) & ChrW(12531) & ChrW(12464) & "(" & ChrW(38651) & ChrW(26609) & ChrW(39006) & ")"
    If shName = SH_LINE Then
        Set wsMap = ThisWorkbook.Sheets(kmLine)
    ElseIf shName = SH_POINT Then
        Set wsMap = ThisWorkbook.Sheets(kmPoint)
    Else
        Set wsMap = ThisWorkbook.Sheets(kmPole)
    End If
    
    ' Read JSON settings
    Dim wsSet As Worksheet: Set wsSet = ThisWorkbook.Sheets(SH_SETTINGS)
    Dim minD As String: minD = CStr(wsSet.Range("B2").Value)
    Dim sEp As String: sEp = CStr(wsSet.Range("B3").Value)
    Dim tEp As String: tEp = CStr(wsSet.Range("B4").Value)
    Dim sEnc As String: sEnc = CStr(wsSet.Range("B5").Value)
    
    Dim DQ As String: DQ = Chr(34)
    Dim T As String: T = "  "
    
    ' === Read existing config.json if exists ===
    Dim existingMappingNames() As String
    Dim existingMappingBlocks() As String
    Dim existingMetaBlocks() As String
    Dim existCount As Long: existCount = 0
    
    Dim sDefault As String: sDefault = ChrW(12487) & ChrW(12501) & ChrW(12457) & ChrW(12523) & ChrW(12488)
    
    If Dir(fp) <> "" Then
        Dim existJson As String: existJson = ReadFileUTF8(fp)
        existCount = ExtractMappings(existJson, existingMappingNames, existingMappingBlocks, existingMetaBlocks)
    End If
    
    ' === Build current sheet mapping ===
    Dim currentMapping As String
    currentMapping = BuildMapping(wsMain, mName, DQ, T, wsMap)
    
    ' === Assemble full JSON ===
    Dim js As String
    js = "{" & vbCrLf
    js = js & T & DQ & "min_distance" & DQ & ": " & minD & "," & vbCrLf
    js = js & T & DQ & "source_epsg" & DQ & ": " & DQ & sEp & DQ & "," & vbCrLf
    js = js & T & DQ & "target_epsg" & DQ & ": " & DQ & tEp & DQ & "," & vbCrLf
    js = js & T & DQ & "source_encoding" & DQ & ": " & DQ & sEnc & DQ & "," & vbCrLf
    
    ' column_mappings
    js = js & T & DQ & "column_mappings" & DQ & ": {" & vbCrLf
    
    ' Default mapping from current sheet
    js = js & T & T & DQ & sDefault & DQ & ": {" & vbCrLf
    Dim defFirst As Boolean: defFirst = True
    Dim lastR As Long: lastR = wsMain.Cells(wsMain.Rows.Count, 1).End(xlUp).Row
    Dim defRow As Long
    For defRow = 9 To lastR
        If wsMain.Cells(defRow, 1).Value = "" Then Exit For
        Dim defKey As String: defKey = LookupKey(wsMap, CStr(wsMain.Cells(defRow, 2).Value))
        If Not defFirst Then js = js & "," & vbCrLf
        js = js & T & T & T & DQ & defKey & DQ & ": {" & vbCrLf
        js = js & T & T & T & T & DQ & "type" & DQ & ": " & DQ & "None" & DQ & vbCrLf
        js = js & T & T & T & "}"
        defFirst = False
    Next defRow
    js = js & vbCrLf & T & T & "}"
    
    ' Existing mappings (skip default and current mName)
    Dim ei As Long
    For ei = 0 To existCount - 1
        If existingMappingNames(ei) <> sDefault And existingMappingNames(ei) <> mName Then
            js = js & "," & vbCrLf & existingMappingBlocks(ei)
        End If
    Next ei
    
    ' Current mapping
    js = js & "," & vbCrLf & currentMapping
    js = js & vbCrLf & T & "}," & vbCrLf
    
    ' column_mappings_meta
    js = js & T & DQ & "column_mappings_meta" & DQ & ": {" & vbCrLf
    js = js & T & T & DQ & sDefault & DQ & ": {" & vbCrLf
    js = js & T & T & T & DQ & "type" & DQ & ": " & DQ & ChrW(32218) & ChrW(35373) & ChrW(20633) & DQ & vbCrLf
    js = js & T & T & "}"
    
    For ei = 0 To existCount - 1
        If existingMappingNames(ei) <> sDefault And existingMappingNames(ei) <> mName Then
            js = js & "," & vbCrLf & existingMetaBlocks(ei)
        End If
    Next ei
    
    js = js & "," & vbCrLf
    js = js & T & T & DQ & mName & DQ & ": {" & vbCrLf
    js = js & T & T & T & DQ & "type" & DQ & ": " & DQ & fType & DQ & vbCrLf
    js = js & T & T & "}"
    js = js & vbCrLf & T & "}," & vbCrLf
    
    js = js & T & DQ & "file_mapping" & DQ & ": {}," & vbCrLf
    js = js & T & DQ & "file_specific_settings" & DQ & ": {}," & vbCrLf
    js = js & T & DQ & "current_mapping_name" & DQ & ": " & DQ & mName & DQ & "," & vbCrLf
    js = js & T & DQ & "file_mappings" & DQ & ": {}" & vbCrLf
    js = js & "}"
    
    WriteFileUTF8 fp, js
    
    MsgBox "config.json " & ChrW(12434) & ChrW(20986) & ChrW(21147) & ChrW(12375) & ChrW(12414) & ChrW(12375) & ChrW(12383) & ChrW(12290) & vbCrLf & ChrW(12510) & ChrW(12483) & ChrW(12500) & ChrW(12531) & ChrW(12464) & ChrW(21517) & ": " & mName & vbCrLf & vbCrLf & ChrW(20986) & ChrW(21147) & ChrW(20808) & ": " & fp, vbInformation, ChrW(20986) & ChrW(21147) & ChrW(23436) & ChrW(20102)
    Exit Sub

ErrHandler:
    MsgBox ChrW(12456) & ChrW(12521) & ChrW(12540) & ChrW(12364) & ChrW(30330) & ChrW(29983) & ChrW(12375) & ChrW(12414) & ChrW(12375) & ChrW(12383) & ChrW(12290) & vbCrLf & vbCrLf & _
           ChrW(12456) & ChrW(12521) & ChrW(12540) & ChrW(30058) & ChrW(21495) & ": " & Err.Number & vbCrLf & _
           ChrW(12456) & ChrW(12521) & ChrW(12540) & ChrW(20869) & ChrW(23481) & ": " & Err.Description & vbCrLf & vbCrLf & _
           ChrW(20986) & ChrW(21147) & ChrW(20808) & ChrW(12497) & ChrW(12473) & ChrW(12434) & ChrW(30906) & ChrW(35469) & ChrW(12375) & ChrW(12390) & ChrW(12367) & ChrW(12384) & ChrW(12373) & ChrW(12356) & ChrW(12290), vbCritical, ChrW(12456) & ChrW(12521) & ChrW(12540)
End Sub

' === Build mapping JSON block for one sheet ===
Private Function BuildMapping(ws As Worksheet, mName As String, DQ As String, T As String, wsMap As Worksheet) As String
    Dim js As String: js = ""
    Dim lastR As Long: lastR = ws.Cells(ws.Rows.Count, 1).End(xlUp).Row
    
    Dim tKaramu As String: tKaramu = ChrW(12459) & ChrW(12521) & ChrW(12512) & ChrW(20195) & ChrW(20837)
    Dim tKaramuS As String: tKaramuS = ChrW(12459) & ChrW(12521) & ChrW(12512) & ChrW(22235) & ChrW(21063) & ChrW(28436) & ChrW(31639)
    Dim tFukusuS As String: tFukusuS = ChrW(35079) & ChrW(25968) & ChrW(12459) & ChrW(12521) & ChrW(12512) & ChrW(22235) & ChrW(21063) & ChrW(28436) & ChrW(31639)
    Dim tTaKar As String: tTaKar = ChrW(35079) & ChrW(25968) & ChrW(12459) & ChrW(12521) & ChrW(12512) & ChrW(25277) & ChrW(20986)
    Dim tJoken As String: tJoken = ChrW(26465) & ChrW(20214) & ChrW(20998) & ChrW(23696)
    Dim tJokenF As String: tJokenF = ChrW(26465) & ChrW(20214) & ChrW(20998) & ChrW(23696) & "_" & ChrW(12501) & ChrW(12449) & ChrW(12452) & ChrW(12523) & ChrW(21517)
    Dim tKotei As String: tKotei = ChrW(22266) & ChrW(23450) & ChrW(20516)
    Dim tFile As String: tFile = ChrW(12501) & ChrW(12449) & ChrW(12452) & ChrW(12523) & ChrW(21517)
    Dim tSeq As String: tSeq = ChrW(12471) & ChrW(12540) & ChrW(12465) & ChrW(12531) & ChrW(12473) & ChrW(20516)
    Dim sFileAttr As String: sFileAttr = ChrW(20837) & ChrW(21147) & ChrW(12501) & ChrW(12449) & ChrW(12452) & ChrW(12523) & ChrW(21517)
    
    js = T & T & DQ & mName & DQ & ": {" & vbCrLf
    Dim first As Boolean: first = True
    Dim dr As Long
    
    For dr = 9 To lastR
        If ws.Cells(dr, 1).Value = "" Then Exit For
        Dim an As String: an = CStr(ws.Cells(dr, 2).Value)
        Dim jsonKey As String: jsonKey = LookupKey(wsMap, an)
        Dim pt As String: pt = CStr(ws.Cells(dr, 3).Value)
        Dim c1 As String: c1 = GC(ws, dr, 4)
        Dim c2 As String: c2 = GC(ws, dr, 5)
        Dim c3 As String: c3 = GC(ws, dr, 6)
        Dim c4 As String: c4 = GC(ws, dr, 7)
        Dim op As String: op = GC(ws, dr, 8)
        Dim cv As String: cv = GC(ws, dr, 9)
        Dim compT As String: compT = GC(ws, dr, 10)
        Dim compFV As String: compFV = GC(ws, dr, 11)
        Dim compC As String: compC = GC(ws, dr, 12)
        Dim btc As String: btc = GC(ws, dr, 14)
        Dim bls As String: bls = GC(ws, dr, 15)
        Dim fv As String: fv = GC(ws, dr, 16)
        Dim sv As String: sv = GC(ws, dr, 18)
        Dim stv As String: stv = GC(ws, dr, 19)
        
        If Not first Then js = js & "," & vbCrLf
        Dim en As String: en = ""
        
        If Left(pt, 2) = "A1" Then
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            If c1 = tFile Or an = sFileAttr Then
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tFile & DQ & "," & vbCrLf
                en = en & T & T & T & T & DQ & "value" & DQ & ": " & DQ & DQ & vbCrLf
            Else
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tKaramu & DQ & "," & vbCrLf
                en = en & T & T & T & T & DQ & "column" & DQ & ": " & DQ & c1 & DQ & vbCrLf
            End If
            en = en & T & T & T & "}"
        ElseIf Left(pt, 2) = "A2" Then
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tKaramuS & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "column" & DQ & ": " & DQ & c1 & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "operator" & DQ & ": " & DQ & op & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "value" & DQ & ": " & DQ & cv & DQ & vbCrLf
            en = en & T & T & T & "}"
        ElseIf Left(pt, 2) = "A3" Then
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tFukusuS & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "column1" & DQ & ": " & DQ & c1 & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "operator" & DQ & ": " & DQ & op & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "column2" & DQ & ": " & DQ & c2 & DQ & vbCrLf
            en = en & T & T & T & "}"
        ElseIf Left(pt, 2) = "A4" Then
            Dim ca As String: ca = ""
            If Not IsDash(c1) Then ca = DQ & c1 & DQ
            If Not IsDash(c2) Then ca = ca & ", " & DQ & c2 & DQ
            If Not IsDash(c3) Then ca = ca & ", " & DQ & c3 & DQ
            If Not IsDash(c4) Then ca = ca & ", " & DQ & c4 & DQ
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tTaKar & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "columns" & DQ & ": [" & ca & "]," & vbCrLf
            en = en & T & T & T & T & DQ & "operator" & DQ & ": " & DQ & op & DQ & vbCrLf
            en = en & T & T & T & "}"
        ElseIf Left(pt, 2) = "B1" Then
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tJoken & DQ & "," & vbCrLf
            en = en & T & T & T & T & DQ & "column" & DQ & ": " & DQ & btc & DQ & "," & vbCrLf
            
            ' Read conditions from list sheet (O column = bls)
            Dim condArr As String: condArr = ""
            Dim defVal As String: defVal = ""
            Dim sOther As String: sOther = ChrW(12381) & ChrW(12428) & ChrW(20197) & ChrW(22806)
            
            If bls <> "" Then
                On Error Resume Next
                Dim wsList As Worksheet: Set wsList = ThisWorkbook.Sheets(bls)
                On Error GoTo 0
                
                If Not wsList Is Nothing Then
                    Dim condFirst As Boolean: condFirst = True
                    Dim lr As Long
                    For lr = 2 To wsList.Cells(wsList.Rows.Count, 1).End(xlUp).Row
                        Dim inVal As String: inVal = Trim(CStr(wsList.Cells(lr, 1).Value))
                        Dim outVal As String: outVal = Trim(CStr(wsList.Cells(lr, 2).Value))
                        If inVal = "" Then Exit For
                        
                        If InStr(inVal, sOther) > 0 Then
                            defVal = outVal
                        Else
                            If Not condFirst Then condArr = condArr & "," & vbCrLf
                            condArr = condArr & T & T & T & T & T & T & "{"
                            condArr = condArr & DQ & "input" & DQ & ": " & DQ & inVal & DQ & ", "
                            condArr = condArr & DQ & "output" & DQ & ": " & DQ & outVal & DQ & "}"
                            condFirst = False
                        End If
                    Next lr
                End If
            End If
            
            If condArr <> "" Then
                en = en & T & T & T & T & DQ & "conditions" & DQ & ": [" & vbCrLf
                en = en & condArr & vbCrLf
                en = en & T & T & T & T & "]," & vbCrLf
            Else
                en = en & T & T & T & T & DQ & "conditions" & DQ & ": []," & vbCrLf
            End If
            en = en & T & T & T & T & DQ & "default" & DQ & ": " & DQ & defVal & DQ & vbCrLf
            en = en & T & T & T & "}"
        ElseIf Left(pt, 2) = "B2" Then
            Dim tFnBr2 As String: tFnBr2 = ChrW(12501) & ChrW(12449) & ChrW(12452) & ChrW(12523) & ChrW(21517) & ChrW(20998) & ChrW(23696)
            Dim sOther2 As String: sOther2 = ChrW(12381) & ChrW(12428) & ChrW(20197) & ChrW(22806)
            
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tFnBr2 & DQ & "," & vbCrLf
            
            ' Read conditions from list sheet (O column = bls)
            Dim fnCondArr As String: fnCondArr = ""
            Dim fnDefVal As String: fnDefVal = ""
            
            If bls <> "" Then
                On Error Resume Next
                Dim wsFnList As Worksheet: Set wsFnList = ThisWorkbook.Sheets(bls)
                On Error GoTo 0
                
                If Not wsFnList Is Nothing Then
                    Dim fnFirst As Boolean: fnFirst = True
                    Dim fnR As Long
                    For fnR = 2 To wsFnList.Cells(wsFnList.Rows.Count, 1).End(xlUp).Row
                        Dim fnIn As String: fnIn = Trim(CStr(wsFnList.Cells(fnR, 1).Value))
                        Dim fnOut As String: fnOut = Trim(CStr(wsFnList.Cells(fnR, 2).Value))
                        If fnIn = "" Then Exit For
                        
                        If InStr(fnIn, sOther2) > 0 Then
                            fnDefVal = fnOut
                        Else
                            If Not fnFirst Then fnCondArr = fnCondArr & "," & vbCrLf
                            fnCondArr = fnCondArr & T & T & T & T & T & T & "{"
                            fnCondArr = fnCondArr & DQ & "filename" & DQ & ": " & DQ & fnIn & DQ & ", "
                            fnCondArr = fnCondArr & DQ & "output" & DQ & ": " & DQ & fnOut & DQ & "}"
                            fnFirst = False
                        End If
                    Next fnR
                End If
            End If
            
            If fnCondArr <> "" Then
                en = en & T & T & T & T & DQ & "conditions" & DQ & ": [" & vbCrLf
                en = en & fnCondArr & vbCrLf
                en = en & T & T & T & T & "]," & vbCrLf
            Else
                en = en & T & T & T & T & DQ & "conditions" & DQ & ": []," & vbCrLf
            End If
            en = en & T & T & T & T & DQ & "default" & DQ & ": " & DQ & fnDefVal & DQ & vbCrLf
            en = en & T & T & T & "}"
        ElseIf Left(pt, 1) = "C" Then
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            If fv = "None" Or fv = "" Then
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & "None" & DQ & vbCrLf
            ElseIf an = sFileAttr Then
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tFile & DQ & "," & vbCrLf
                en = en & T & T & T & T & DQ & "value" & DQ & ": " & DQ & fv & DQ & vbCrLf
            Else
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tKotei & DQ & "," & vbCrLf
                en = en & T & T & T & T & DQ & "value" & DQ & ": " & DQ & fv & DQ & vbCrLf
            End If
            en = en & T & T & T & "}"
        ElseIf Left(pt, 1) = "D" Then
            Dim sSeqWord As String: sSeqWord = ChrW(12471) & ChrW(12540) & ChrW(12465) & ChrW(12531) & ChrW(12473)
            Dim nb2 As String: nb2 = GC(ws, dr, 17)
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            If InStr(nb2, sSeqWord) > 0 Then
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tSeq & DQ & "," & vbCrLf
                en = en & T & T & T & T & DQ & "start" & DQ & ": " & DQ & sv & DQ & "," & vbCrLf
                en = en & T & T & T & T & DQ & "step" & DQ & ": " & DQ & stv & DQ & vbCrLf
            Else
                en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & "None" & DQ & vbCrLf
            End If
            en = en & T & T & T & "}"
        Else
            en = T & T & T & DQ & jsonKey & DQ & ": {" & vbCrLf
            en = en & T & T & T & T & DQ & "type" & DQ & ": " & DQ & "None" & DQ & vbCrLf
            en = en & T & T & T & "}"
        End If
        
        ' Fallback
        Dim hasFB As Boolean: hasFB = False
        If Len(compT) > 0 Then
            If InStr(compT, ChrW(950)) = 0 Then hasFB = True
        End If
        If hasFB Then
            en = Left(en, Len(en) - 1)
            Do While Right(en, 1) = vbLf Or Right(en, 1) = vbCr Or Right(en, 1) = " "
                en = Left(en, Len(en) - 1)
            Loop
            en = en & "," & vbCrLf
            en = en & T & T & T & T & DQ & "fallback" & DQ & ": {" & vbCrLf
            If InStr(compT, ChrW(946)) > 0 Then
                ' beta: column condition branch fallback
                Dim tColBranch As String: tColBranch = ChrW(12459) & ChrW(12521) & ChrW(12512) & ChrW(26465) & ChrW(20214) & ChrW(20998) & ChrW(23696)
                Dim betaSh As String: betaSh = GC(ws, dr, 13)
                
                en = en & T & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tColBranch & DQ & "," & vbCrLf
                en = en & T & T & T & T & T & DQ & "column" & DQ & ": " & DQ & compC & DQ & "," & vbCrLf
                
                ' Read conditions from list sheet if specified
                Dim betaCondArr As String: betaCondArr = ""
                Dim betaDefVal As String: betaDefVal = ""
                Dim sOtherB As String: sOtherB = ChrW(12381) & ChrW(12428) & ChrW(20197) & ChrW(22806)
                
                If betaSh <> "" Then
                    On Error Resume Next
                    Dim wsBList As Worksheet: Set wsBList = ThisWorkbook.Sheets(betaSh)
                    On Error GoTo 0
                    
                    If Not wsBList Is Nothing Then
                        Dim bFirst As Boolean: bFirst = True
                        Dim bR As Long
                        For bR = 2 To wsBList.Cells(wsBList.Rows.Count, 1).End(xlUp).Row
                            Dim bIn As String: bIn = Trim(CStr(wsBList.Cells(bR, 1).Value))
                            Dim bOut As String: bOut = Trim(CStr(wsBList.Cells(bR, 2).Value))
                            If bIn = "" Then Exit For
                            If InStr(bIn, sOtherB) > 0 Then
                                betaDefVal = bOut
                            Else
                                If Not bFirst Then betaCondArr = betaCondArr & "," & vbCrLf
                                betaCondArr = betaCondArr & T & T & T & T & T & T & T & "{"
                                betaCondArr = betaCondArr & DQ & "input" & DQ & ": " & DQ & bIn & DQ & ", "
                                betaCondArr = betaCondArr & DQ & "output" & DQ & ": " & DQ & bOut & DQ & "}"
                                bFirst = False
                            End If
                        Next bR
                    End If
                End If
                
                If betaCondArr <> "" Then
                    en = en & T & T & T & T & T & DQ & "conditions" & DQ & ": [" & vbCrLf
                    en = en & betaCondArr & vbCrLf
                    en = en & T & T & T & T & T & "]," & vbCrLf
                Else
                    en = en & T & T & T & T & T & DQ & "conditions" & DQ & ": []," & vbCrLf
                End If
                en = en & T & T & T & T & T & DQ & "default" & DQ & ": " & DQ & betaDefVal & DQ & vbCrLf
            ElseIf InStr(compT, ChrW(947)) > 0 Then
                ' gamma: filename mapping fallback - read list sheet from M column
                Dim tFnBranch As String: tFnBranch = ChrW(12501) & ChrW(12449) & ChrW(12452) & ChrW(12523) & ChrW(21517) & ChrW(20998) & ChrW(23696)
                Dim compSh As String: compSh = GC(ws, dr, 13)
                Dim fnMapStr As String: fnMapStr = ""
                Dim sOtherG As String: sOtherG = ChrW(12381) & ChrW(12428) & ChrW(20197) & ChrW(22806)
                
                If compSh <> "" Then
                    On Error Resume Next
                    Dim wsGList As Worksheet: Set wsGList = ThisWorkbook.Sheets(compSh)
                    On Error GoTo 0
                    
                    If Not wsGList Is Nothing Then
                        Dim gR As Long
                        For gR = 2 To wsGList.Cells(wsGList.Rows.Count, 1).End(xlUp).Row
                            Dim gIn As String: gIn = Trim(CStr(wsGList.Cells(gR, 1).Value))
                            Dim gOut As String: gOut = Trim(CStr(wsGList.Cells(gR, 2).Value))
                            If gIn = "" Then Exit For
                            If InStr(gIn, sOtherG) = 0 Then
                                If fnMapStr <> "" Then fnMapStr = fnMapStr & ","
                                fnMapStr = fnMapStr & gIn & "=" & gOut
                            End If
                        Next gR
                    End If
                End If
                
                en = en & T & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tFnBranch & DQ & "," & vbCrLf
                en = en & T & T & T & T & T & DQ & "filename_mapping" & DQ & ": " & DQ & fnMapStr & DQ & vbCrLf
            Else
                ' alpha: fixed value fallback
                Dim fbV As String: fbV = compFV: If fbV = "" Then fbV = "0"
                en = en & T & T & T & T & T & DQ & "type" & DQ & ": " & DQ & tKotei & DQ & "," & vbCrLf
                en = en & T & T & T & T & T & DQ & "value" & DQ & ": " & DQ & fbV & DQ & vbCrLf
            End If
            en = en & T & T & T & T & "}" & vbCrLf
            en = en & T & T & T & "}"
        End If
        
        js = js & en
        first = False
    Next dr
    js = js & vbCrLf & T & T & "}"
    BuildMapping = js
End Function

' === Extract existing mappings using line-by-line parsing ===
Private Function ExtractMappings(json As String, ByRef names() As String, ByRef blocks() As String, ByRef metas() As String) As Long
    Dim lines() As String: lines = Split(json, vbLf)
    Dim DQ As String: DQ = Chr(34)
    Dim count As Long: count = 0
    Dim maxItems As Long: maxItems = 50
    ReDim names(maxItems - 1)
    ReDim blocks(maxItems - 1)
    ReDim metas(maxItems - 1)
    
    ' Phase 1: Find column_mappings section and extract mapping blocks
    Dim inCM As Boolean: inCM = False
    Dim depth As Long: depth = 0
    Dim captName As String: captName = ""
    Dim captBlock As String: captBlock = ""
    Dim captDepth As Long: captDepth = 0
    Dim capturing As Boolean: capturing = False
    
    Dim i As Long
    For i = 0 To UBound(lines)
        Dim ln As String: ln = Replace(lines(i), vbCr, "")
        
        ' Detect column_mappings section start
        If InStr(ln, DQ & "column_mappings" & DQ & ":") > 0 And InStr(ln, "meta") = 0 Then
            inCM = True
            depth = 0
        End If
        
        If Not inCM Then GoTo NextLine1
        
        ' Count braces
        Dim ci As Long
        For ci = 1 To Len(ln)
            Dim ch As String: ch = Mid(ln, ci, 1)
            If ch = "{" Then depth = depth + 1
            If ch = "}" Then depth = depth - 1
        Next ci
        
        ' depth=0 means we left column_mappings
        If depth <= 0 And i > 0 Then inCM = False: GoTo NextLine1
        
        ' At depth=2 start, we found a mapping name (depth goes 1->2 when we enter a mapping)
        If Not capturing Then
            ' Look for pattern: 4-space + "name": {
            Dim trimLn As String: trimLn = ln
            ' Check if this line starts a new mapping (exactly 4 leading spaces)
            If Len(ln) >= 5 Then
                If Left(ln, 4) = "    " And Mid(ln, 5, 1) = DQ Then
                    ' Extract name
                    Dim ns As Long: ns = InStr(ln, DQ) + 1
                    Dim ne As Long: ne = InStr(ns, ln, DQ)
                    If ne > ns Then
                        captName = Mid(ln, ns, ne - ns)
                        captBlock = ln
                        captDepth = 0
                        Dim cj As Long
                        For cj = 1 To Len(ln)
                            If Mid(ln, cj, 1) = "{" Then captDepth = captDepth + 1
                            If Mid(ln, cj, 1) = "}" Then captDepth = captDepth - 1
                        Next cj
                        If captDepth > 0 Then
                            capturing = True
                        End If
                    End If
                End If
            End If
        Else
            captBlock = captBlock & vbCrLf & ln
            For cj = 1 To Len(ln)
                If Mid(ln, cj, 1) = "{" Then captDepth = captDepth + 1
                If Mid(ln, cj, 1) = "}" Then captDepth = captDepth - 1
            Next cj
            If captDepth <= 0 Then
                ' Capture complete
                If count < maxItems Then
                    names(count) = captName
                    blocks(count) = TrimTrailingComma(captBlock)
                    count = count + 1
                End If
                capturing = False
            End If
        End If
NextLine1:
    Next i
    
    ' Phase 2: Extract meta blocks similarly
    Dim inMeta As Boolean: inMeta = False
    depth = 0
    capturing = False
    Dim metaIdx As Long: metaIdx = 0
    
    For i = 0 To UBound(lines)
        ln = Replace(lines(i), vbCr, "")
        
        If InStr(ln, DQ & "column_mappings_meta" & DQ & ":") > 0 Then
            inMeta = True: depth = 0
        End If
        
        If Not inMeta Then GoTo NextLine2
        
        For ci = 1 To Len(ln)
            ch = Mid(ln, ci, 1)
            If ch = "{" Then depth = depth + 1
            If ch = "}" Then depth = depth - 1
        Next ci
        
        If depth <= 0 And i > 0 Then inMeta = False: GoTo NextLine2
        
        If Not capturing Then
            If Len(ln) >= 5 Then
                If Left(ln, 4) = "    " And Mid(ln, 5, 1) = DQ Then
                    ns = InStr(ln, DQ) + 1
                    ne = InStr(ns, ln, DQ)
                    If ne > ns Then
                        captName = Mid(ln, ns, ne - ns)
                        captBlock = ln
                        captDepth = 0
                        For cj = 1 To Len(ln)
                            If Mid(ln, cj, 1) = "{" Then captDepth = captDepth + 1
                            If Mid(ln, cj, 1) = "}" Then captDepth = captDepth - 1
                        Next cj
                        If captDepth > 0 Then
                            capturing = True
                        Else
                            ' Single line meta
                            Dim mIdx As Long
                            For mIdx = 0 To count - 1
                                If names(mIdx) = captName Then
                                    metas(mIdx) = TrimTrailingComma(captBlock)
                                    Exit For
                                End If
                            Next mIdx
                        End If
                    End If
                End If
            End If
        Else
            captBlock = captBlock & vbCrLf & ln
            For cj = 1 To Len(ln)
                If Mid(ln, cj, 1) = "{" Then captDepth = captDepth + 1
                If Mid(ln, cj, 1) = "}" Then captDepth = captDepth - 1
            Next cj
            If captDepth <= 0 Then
                For mIdx = 0 To count - 1
                    If names(mIdx) = captName Then
                        metas(mIdx) = TrimTrailingComma(captBlock)
                        Exit For
                    End If
                Next mIdx
                capturing = False
            End If
        End If
NextLine2:
    Next i
    
    ExtractMappings = count
End Function

' === File I/O ===
Private Function ReadFileUTF8(filePath As String) As String
    Dim stm As Object: Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2: stm.Charset = "UTF-8": stm.Open
    stm.LoadFromFile filePath
    ReadFileUTF8 = stm.ReadText
    stm.Close: Set stm = Nothing
End Function

Private Sub WriteFileUTF8(filePath As String, content As String)
    Dim stm As Object: Set stm = CreateObject("ADODB.Stream")
    stm.Type = 2: stm.Charset = "UTF-8": stm.Open: stm.WriteText content
    stm.Position = 0: stm.Type = 1: stm.Position = 3
    Dim binData() As Byte: binData = stm.Read: stm.Close
    Dim stmOut As Object: Set stmOut = CreateObject("ADODB.Stream")
    stmOut.Type = 1: stmOut.Open: stmOut.Write binData
    stmOut.SaveToFile filePath, 2: stmOut.Close
    Set stmOut = Nothing: Set stm = Nothing
End Sub

Private Function GC(ws As Worksheet, r As Long, c As Long) As String
    Dim v As Variant: v = ws.Cells(r, c).Value
    If IsEmpty(v) Or IsNull(v) Then GC = "" Else GC = Trim(CStr(v))
End Function


Private Function TrimTrailingComma(s As String) As String
    Dim result As String: result = s
    ' Remove trailing whitespace/newlines
    Do While Len(result) > 0
        Dim last As String: last = Right(result, 1)
        If last = vbLf Or last = vbCr Or last = " " Or last = Chr(9) Then
            result = Left(result, Len(result) - 1)
        Else
            Exit Do
        End If
    Loop
    ' Remove ALL trailing commas
    Do While Len(result) > 0 And Right(result, 1) = ","
        result = Left(result, Len(result) - 1)
    Loop
    TrimTrailingComma = result
End Function

Private Function LookupKey(wsMap As Worksheet, jpName As String) As String
    ' Look up English key from key mapping sheet
    Dim r As Long
    For r = 2 To wsMap.Cells(wsMap.Rows.Count, 1).End(xlUp).Row
        If CStr(wsMap.Cells(r, 1).Value) = jpName Then
            LookupKey = CStr(wsMap.Cells(r, 2).Value)
            Exit Function
        End If
    Next r
    ' If not found, use Japanese name as-is
    LookupKey = jpName
End Function

Private Function IsDash(s As String) As Boolean
    IsDash = (s = "-" Or s = ChrW(65293) Or s = "")
End Function
