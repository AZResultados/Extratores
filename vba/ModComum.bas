Attribute VB_Name = "ModComum"
' =============================================================================
' ModComum - Funções compartilhadas entre todos os extratores
' =============================================================================

Sub ProcessarExtrator(celulaScript As String, nomeExtrator As String)

    Dim wsDados    As Worksheet
    Dim wsConfig   As Worksheet
    Dim pythonExe  As String
    Dim scriptPath As String
    Dim jsonOutput As String
    Dim tempFile   As String
    Dim cmd        As String

    Set wsDados = ThisWorkbook.Sheets("LctosTratados")
    Set wsConfig = ThisWorkbook.Sheets("Config")

    pythonExe = wsConfig.Range("B1").Value
    scriptPath = wsConfig.Range(celulaScript).Value
    tempFile = "C:\Temp\extratores_output.json"

    If Dir("C:\Temp", vbDirectory) = "" Then MkDir "C:\Temp"

    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & pythonExe & Chr(34) & " " & _
          Chr(34) & scriptPath & Chr(34) & " > " & _
          Chr(34) & tempFile & Chr(34)

    Dim wsh As Object
    Set wsh = CreateObject("WScript.Shell")
    wsh.Run cmd, 1, True

    If Dir(tempFile) = "" Then
        MsgBox "Operacao cancelada ou erro ao executar " & nomeExtrator & ".", vbExclamation
        Exit Sub
    End If

    ' Le JSON em UTF-8
    Dim stream As Object
    Set stream = CreateObject("ADODB.Stream")
    stream.Charset = "UTF-8"
    stream.Open
    stream.LoadFromFile tempFile
    jsonOutput = stream.ReadText
    stream.Close

    ' Verifica erro critico
    Dim chaveErro  As String
    Dim chaveErros As String
    chaveErro = Chr(34) & "erro" & Chr(34)
    chaveErros = Chr(34) & "erros" & Chr(34)
    If InStr(jsonOutput, chaveErro) > 0 And InStr(jsonOutput, chaveErros) = 0 Then
        MsgBox "Erro retornado pelo Python:" & vbCrLf & jsonOutput, vbCritical
        Exit Sub
    End If

    ' Limpa dados anteriores
    Dim lastRow As Long
    lastRow = wsDados.Cells(wsDados.Rows.Count, 1).End(xlUp).Row
    If lastRow > 1 Then wsDados.Rows("2:" & lastRow).Delete

    ' Localiza array de lancamentos
    Dim chaveArray As String
    chaveArray = Chr(34) & "lancamentos" & Chr(34) & ": ["

    Dim posArray As Long
    Dim posStart As Long
    Dim posEnd   As Long
    Dim errosPos As Long
    Dim objStr   As String
    Dim rowNum   As Long

    rowNum = 2
    posArray = InStr(jsonOutput, chaveArray)
    errosPos = InStr(jsonOutput, chaveErros)
    posStart = InStr(posArray, jsonOutput, "{")

    Do While posStart > 0 And posStart < errosPos
        posEnd = InStr(posStart, jsonOutput, "}")
        If posEnd = 0 Or posEnd > errosPos Then Exit Do

        objStr = Mid(jsonOutput, posStart, posEnd - posStart + 1)

        Dim fArquivo As String
        Dim fVenc    As String
        Dim fDesc    As String
        Dim fValor   As String
        Dim fTipo    As String
        Dim fTitular As String

        fArquivo = ExtrairCampo(objStr, "arquivo_origem")
        fVenc = ExtrairCampo(objStr, "data_vencimento")
        fDesc = ExtrairCampo(objStr, "descricao")
        fValor = ExtrairCampo(objStr, "valor_brl")
        fTipo = ExtrairCampo(objStr, "tipo")
        fTitular = ExtrairCampo(objStr, "titular_cartao")
        If fTitular = "" Then fTitular = "ND"

        With wsDados
            .Cells(rowNum, 1).Value = fArquivo
            .Cells(rowNum, 2).Value = CDate(fVenc)
            .Cells(rowNum, 2).NumberFormat = "dd/mm/yyyy"
            .Cells(rowNum, 3).Value = fDesc
            .Cells(rowNum, 4).Value = CDbl(Replace(fValor, ".", ","))
            .Cells(rowNum, 4).NumberFormat = "#,##0.00"
            .Cells(rowNum, 5).Value = fTipo
            .Cells(rowNum, 6).Value = fTitular

            Dim fillColor As Long
            If rowNum Mod 2 = 0 Then
                fillColor = RGB(235, 243, 255)
            Else
                fillColor = RGB(255, 255, 255)
            End If

            Dim c As Integer
            For c = 1 To 6
                .Cells(rowNum, c).Interior.Color = fillColor
            Next c
        End With

        rowNum = rowNum + 1
        posStart = InStr(posEnd, jsonOutput, "{")
    Loop

    ' Verifica erros reportados
    Dim errosStr As String
    errosStr = ExtrairArray(jsonOutput, "erros")
    If Len(errosStr) > 2 Then
        MsgBox "Concluido com avisos:" & vbCrLf & errosStr, vbExclamation
    Else
        MsgBox (rowNum - 2) & " lancamentos importados com sucesso! (" & nomeExtrator & ")", vbInformation
    End If

    Kill tempFile
    wsDados.Activate
    wsDados.Cells(2, 1).Select

End Sub


Function ExtrairCampo(jsonObj As String, campo As String) As String
    Dim chave  As String
    Dim pos    As Long
    Dim posVal As Long
    Dim posEnd As Long

    chave = Chr(34) & campo & Chr(34) & ":"
    pos = InStr(jsonObj, chave)
    If pos = 0 Then ExtrairCampo = "": Exit Function

    posVal = pos + Len(chave)
    Do While Mid(jsonObj, posVal, 1) = " "
        posVal = posVal + 1
    Loop

    If Mid(jsonObj, posVal, 1) = Chr(34) Then
        posVal = posVal + 1
        posEnd = InStr(posVal, jsonObj, Chr(34))
        ExtrairCampo = Replace(Mid(jsonObj, posVal, posEnd - posVal), "\\", "\")
    Else
        posEnd = posVal
        Do While Mid(jsonObj, posEnd, 1) Like "[0-9.\\-]"
            posEnd = posEnd + 1
        Loop
        ExtrairCampo = Mid(jsonObj, posVal, posEnd - posVal)
    End If
End Function


Function ExtrairArray(jsonStr As String, campo As String) As String
    Dim chave  As String
    Dim pos    As Long
    Dim posEnd As Long
    chave = Chr(34) & campo & Chr(34) & ": ["
    pos = InStr(jsonStr, chave)
    If pos = 0 Then ExtrairArray = "[]": Exit Function
    pos = InStr(pos, jsonStr, "[")
    posEnd = InStr(pos, jsonStr, "]")
    ExtrairArray = Mid(jsonStr, pos, posEnd - pos + 1)
End Function
