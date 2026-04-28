Attribute VB_Name = "ModComum"
' =============================================================================
' ModComum - Funções compartilhadas entre todos os extratores
' =============================================================================
' Config layout esperado:
'   B1 = caminho pythonExe
'   B2 = caminho script Mercado Pago
'   B3 = caminho script Santander
'   B4 = nomeCliente  (ex: "JW")
'   B5 = inputDir Mercado Pago
'   B6 = inputDir Santander
' Senhas layout esperado:
'   B1 = senha Santander (CPF/CNPJ do titular) — em branco se não criptografado

Sub ProcessarExtrator(celulaScript As String, nomeExtrator As String, _
                      nomeCliente As String, inputDir As String, _
                      Optional senha As String = "")

    Dim wsConfig   As Worksheet
    Dim wsDados    As Worksheet
    Dim pythonExe  As String
    Dim scriptPath As String
    Dim cmd        As String
    Dim jsonStr    As String
    Dim errStr     As String

    Set wsConfig = ThisWorkbook.Sheets("Config")
    Set wsDados  = ThisWorkbook.Sheets("LctosTratados")

    pythonExe  = wsConfig.Range("B1").Value
    scriptPath = wsConfig.Range(celulaScript).Value

    ' -------------------------------------------------------------------------
    ' Monta comando CLI (BR-02)
    ' -------------------------------------------------------------------------
    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & pythonExe  & Chr(34) & " " & _
          Chr(34) & scriptPath & Chr(34) & _
          " --cliente "   & Chr(34) & nomeCliente & Chr(34) & _
          " --input-dir " & Chr(34) & inputDir    & Chr(34)

    If Len(Trim(senha)) > 0 Then
        cmd = cmd & " --password " & Chr(34) & senha & Chr(34)
    End If

    ' -------------------------------------------------------------------------
    ' Exec() — captura stdout/stderr, zero arquivo temporário (BR-06)
    ' ORDEM OBRIGATÓRIA: StdOut.ReadAll antes de ExitCode (previne deadlock pipe)
    ' -------------------------------------------------------------------------
    Dim oShell As Object
    Dim oExec  As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)

    jsonStr = oExec.StdOut.ReadAll
    errStr  = oExec.StdErr.ReadAll

    ' -------------------------------------------------------------------------
    ' Fail-fast (BR-03): ExitCode <> 0 → aborta, zero gravação
    ' -------------------------------------------------------------------------
    If oExec.ExitCode <> 0 Then
        MsgBox "ERRO ao executar " & nomeExtrator & ":" & vbCrLf & errStr, vbCritical
        Exit Sub
    End If

    ' ExitCode = 0 com stderr não-vazio → aviso técnico (não aborta)
    If Len(Trim(errStr)) > 0 Then
        MsgBox "Aviso técnico (" & nomeExtrator & "):" & vbCrLf & errStr, vbExclamation
    End If

    ' -------------------------------------------------------------------------
    ' Verifica avisos do envelope (não-fatais)
    ' -------------------------------------------------------------------------
    Dim avisosStr As String
    avisosStr = ExtrairArray(jsonStr, "avisos")
    If Len(avisosStr) > 2 Then
        MsgBox "Avisos (" & nomeExtrator & "):" & vbCrLf & avisosStr, vbExclamation
    End If

    ' -------------------------------------------------------------------------
    ' Migração automática de schema
    ' A1 <> "Cliente" → renomeia aba legado, cria nova com cabeçalho
    ' -------------------------------------------------------------------------
    If wsDados.Cells(1, 1).Value <> "Cliente" Then
        On Error Resume Next
        wsDados.Name = "LctosTratados_legado"
        On Error GoTo 0

        Dim wsNova As Worksheet
        Set wsNova = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsNova.Name = "LctosTratados"
        wsNova.Cells(1, 1).Value = "Cliente"
        wsNova.Cells(1, 2).Value = "ID_Lote"
        wsNova.Cells(1, 3).Value = "Arquivo Origem"
        wsNova.Cells(1, 4).Value = "Data Vencimento"
        wsNova.Cells(1, 5).Value = "Descri" & Chr(231) & Chr(227) & "o"
        wsNova.Cells(1, 6).Value = "Parcela"
        wsNova.Cells(1, 7).Value = "Valor (R$)"
        wsNova.Cells(1, 8).Value = "Tipo"
        wsNova.Cells(1, 9).Value = "Titular - Cart" & Chr(227) & "o"
        wsNova.Rows(1).Font.Bold = True
        Set wsDados = wsNova
    End If

    ' -------------------------------------------------------------------------
    ' APPEND acumulativo — nunca deletar linhas existentes
    ' Rollback: deletar manualmente linhas onde Col B = id_lote indesejado
    ' Colunas: A=cliente  B=id_lote  C=arquivo  D=vencimento  E=descricao
    '          F=parcela  G=valor    H=tipo      I=titular_cartao
    ' -------------------------------------------------------------------------
    Dim chaveArray As String
    Dim posArray   As Long
    Dim posStart   As Long
    Dim posEnd     As Long
    Dim objStr     As String
    Dim rowNum     As Long
    Dim lastRow    As Long

    lastRow = wsDados.Cells(wsDados.Rows.Count, "A").End(xlUp).Row + 1

    chaveArray = Chr(34) & "lancamentos" & Chr(34) & ": ["
    rowNum   = lastRow
    posArray = InStr(jsonStr, chaveArray)
    posStart = InStr(posArray, jsonStr, "{")

    Do While posStart > 0
        posEnd = InStr(posStart, jsonStr, "}")
        If posEnd = 0 Then Exit Do

        objStr = Mid(jsonStr, posStart, posEnd - posStart + 1)

        Dim fCliente As String
        Dim fIdLote  As String
        Dim fArquivo As String
        Dim fVenc    As String
        Dim fDesc    As String
        Dim fParcela As String
        Dim fValor   As String
        Dim fTipo    As String
        Dim fTitular As String

        fCliente = ExtrairCampo(objStr, "cliente")
        fIdLote  = ExtrairCampo(objStr, "id_lote")
        fArquivo = ExtrairCampo(objStr, "arquivo")
        fVenc    = ExtrairCampo(objStr, "vencimento")
        fDesc    = ExtrairCampo(objStr, "descricao")
        fParcela = ExtrairCampo(objStr, "parcela")
        fValor   = ExtrairCampo(objStr, "valor")
        fTipo    = ExtrairCampo(objStr, "tipo")
        fTitular = ExtrairCampo(objStr, "titular_cartao")

        With wsDados
            .Cells(rowNum, 1).Value = fCliente
            .Cells(rowNum, 2).Value = fIdLote
            .Cells(rowNum, 3).Value = fArquivo
            .Cells(rowNum, 4).Value = CDate(fVenc)
            .Cells(rowNum, 4).NumberFormat = "dd/mm/yyyy"
            .Cells(rowNum, 5).Value = fDesc
            .Cells(rowNum, 6).Value = fParcela
            .Cells(rowNum, 7).Value = CDbl(Replace(fValor, ".", ","))
            .Cells(rowNum, 7).NumberFormat = "#,##0.00"
            .Cells(rowNum, 8).Value = fTipo
            .Cells(rowNum, 9).Value = fTitular
        End With

        rowNum   = rowNum + 1
        posStart = InStr(posEnd, jsonStr, "{")
    Loop

    MsgBox (rowNum - lastRow) & " lancamentos importados (" & nomeExtrator & ")", vbInformation

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
