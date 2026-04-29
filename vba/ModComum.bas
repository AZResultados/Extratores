Attribute VB_Name = "ModComum"
' =============================================================================
' ModComum - Processamento central + utilitarios compartilhados
' Caminhos via ModConfig — sem dependencia de aba Config
' =============================================================================

Sub ProcessarExtrator(nomeCliente As String, inputDir As String)

    Dim cmd     As String
    Dim jsonStr As String
    Dim errStr  As String

    Dim wsDados As Worksheet

    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & PythonExe()      & Chr(34) & " " & _
          Chr(34) & ExtratorScript() & Chr(34) & _
          " --cliente "   & Chr(34) & nomeCliente & Chr(34) & _
          " --input-dir " & Chr(34) & inputDir    & Chr(34)

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)

    oExec.StdIn.Close

    jsonStr = oExec.StdOut.ReadAll
    errStr  = oExec.StdErr.ReadAll

    If oExec.ExitCode <> 0 Then
        MsgBox "ERRO ao processar " & nomeCliente & ":" & vbCrLf & errStr, vbCritical
        Exit Sub
    End If

    If Len(Trim(errStr)) > 0 Then
        MsgBox "Aviso tecnico:" & vbCrLf & errStr, vbExclamation
    End If

    Dim sc As Object
    Set sc = CreateObject("MSScriptControl.ScriptControl")
    sc.Language = "JScript"

    On Error GoTo ErroParse
    sc.ExecuteStatement "var env = " & jsonStr
    On Error GoTo 0

    Dim avisosLen As Long
    Dim avisosMsg As String
    Dim j         As Long
    avisosLen = sc.Eval("env.avisos.length")
    If avisosLen > 0 Then
        For j = 0 To avisosLen - 1
            avisosMsg = avisosMsg & sc.Eval("env.avisos[" & j & "]") & vbCrLf
        Next j
        MsgBox "Avisos:" & vbCrLf & avisosMsg, vbExclamation
    End If

    On Error Resume Next
    Set wsDados = ThisWorkbook.Sheets("LctosTratados")
    On Error GoTo 0

    If wsDados Is Nothing Then
        ' Primeira execucao: aba ainda nao existe
        Set wsDados = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsDados.Name = "LctosTratados"
        Call _CriarCabecalho(wsDados)
    ElseIf wsDados.Cells(1, 1).Value <> "Cliente" Then
        ' Aba existe mas com schema antigo: preserva como legado
        On Error Resume Next
        wsDados.Name = "LctosTratados_legado"
        On Error GoTo 0
        Set wsDados = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsDados.Name = "LctosTratados"
        Call _CriarCabecalho(wsDados)
    End If

    Dim total   As Long
    Dim rowNum  As Long
    Dim lastRow As Long
    Dim i       As Long
    Dim prefix  As String

    lastRow = wsDados.Cells(wsDados.Rows.Count, "A").End(xlUp).Row + 1
    rowNum  = lastRow
    total   = sc.Eval("env.lancamentos.length")

    For i = 0 To total - 1
        prefix = "env.lancamentos[" & i & "]."
        With wsDados
            .Cells(rowNum, 1).Value = sc.Eval(prefix & "cliente")
            .Cells(rowNum, 2).Value = sc.Eval(prefix & "id_lote")
            .Cells(rowNum, 3).Value = sc.Eval(prefix & "arquivo")
            .Cells(rowNum, 4).Value = CDate(sc.Eval(prefix & "vencimento"))
            .Cells(rowNum, 4).NumberFormat = "dd/mm/yyyy"
            .Cells(rowNum, 5).Value = sc.Eval(prefix & "descricao")
            .Cells(rowNum, 6).Value = sc.Eval("env.lancamentos[" & i & "].parcela || ''")
            .Cells(rowNum, 7).Value = CDbl(sc.Eval(prefix & "valor"))
            .Cells(rowNum, 7).NumberFormat = "#,##0.00"
            .Cells(rowNum, 8).Value = sc.Eval(prefix & "tipo")
            .Cells(rowNum, 9).Value = sc.Eval(prefix & "titular_cartao")
        End With
        rowNum = rowNum + 1
    Next i

    MsgBox (rowNum - lastRow) & " lancamentos importados para " & nomeCliente, vbInformation
    wsDados.Activate
    wsDados.Cells(2, 1).Select
    Exit Sub

ErroParse:
    MsgBox "ERRO: JSON invalido recebido do Python." & vbCrLf & _
           "Primeiros 200 chars: " & Left(jsonStr, 200), vbCritical
End Sub


' =============================================================================
' Utilitarios compartilhados
' =============================================================================

Function ObterListaClientes() As String()
    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec = oShell.Exec("cmd /c chcp 65001 > nul && " & _
                Chr(34) & PythonExe() & Chr(34) & " " & _
                Chr(34) & SetupClienteScript() & Chr(34) & " list")
    oExec.StdIn.Close

    Dim saida As String
    saida = Replace(Trim(oExec.StdOut.ReadAll), vbCr, "")

    Dim vazio(0) As String
    vazio(0) = ""

    If saida = "" Or saida = "VAZIO" Then
        ObterListaClientes = vazio
        Exit Function
    End If

    Dim linhas() As String
    linhas = Split(saida, vbLf)

    Dim validos() As String
    ReDim validos(UBound(linhas))
    Dim n As Integer, k As Integer
    n = 0
    For k = 0 To UBound(linhas)
        If Trim(linhas(k)) <> "" And Trim(linhas(k)) <> "VAZIO" Then
            validos(n) = Trim(linhas(k))
            n = n + 1
        End If
    Next k

    If n = 0 Then
        ObterListaClientes = vazio
        Exit Function
    End If

    ReDim Preserve validos(n - 1)
    ObterListaClientes = validos
End Function


Function SelecionarCliente(ByRef outBaseDir As String) As String
    SelecionarCliente = ""
    outBaseDir = ""

    Dim clientes() As String
    clientes = ObterListaClientes()

    If clientes(0) = "" Then
        MsgBox "Nenhum cliente cadastrado." & vbCrLf & _
               "Use o botao 'Cadastrar Cliente' primeiro.", vbExclamation
        Exit Function
    End If

    Dim lista As String
    Dim i As Integer
    For i = 0 To UBound(clientes)
        Dim p() As String
        p = Split(clientes(i), "|")
        lista = lista & "  " & (i + 1) & ". " & p(0) & vbCrLf
    Next i

    Dim escolha As String
    escolha = InputBox("Clientes cadastrados:" & vbCrLf & vbCrLf & _
                       lista & vbCrLf & "Digite o numero:", "Selecionar Cliente")

    If Trim(escolha) = "" Then Exit Function
    If Not IsNumeric(escolha) Then
        MsgBox "Entrada invalida.", vbExclamation
        Exit Function
    End If

    Dim idx As Integer
    idx = CInt(escolha) - 1
    If idx < 0 Or idx > UBound(clientes) Then
        MsgBox "Numero fora do intervalo.", vbExclamation
        Exit Function
    End If

    Dim sel() As String
    sel = Split(clientes(idx), "|")
    SelecionarCliente = sel(0)
    If UBound(sel) >= 1 Then outBaseDir = sel(1)
End Function


Private Sub _CriarCabecalho(ws As Worksheet)
    ws.Cells(1, 1).Value = "Cliente"
    ws.Cells(1, 2).Value = "ID_Lote"
    ws.Cells(1, 3).Value = "Arquivo Origem"
    ws.Cells(1, 4).Value = "Data Vencimento"
    ws.Cells(1, 5).Value = "Descri" & Chr(231) & Chr(227) & "o"
    ws.Cells(1, 6).Value = "Parcela"
    ws.Cells(1, 7).Value = "Valor (R$)"
    ws.Cells(1, 8).Value = "Tipo"
    ws.Cells(1, 9).Value = "Titular - Cart" & Chr(227) & "o"
    ws.Rows(1).Font.Bold = True
End Sub


Function SelecionarPasta(titulo As String, Optional startPath As String = "") As String
    SelecionarPasta = ""
    Dim oShell As Object
    Set oShell = CreateObject("Shell.Application")
    Dim oFolder As Object
    If startPath <> "" Then
        Set oFolder = oShell.BrowseForFolder(0, titulo, 0, startPath)
    Else
        Set oFolder = oShell.BrowseForFolder(0, titulo, 0)
    End If
    If Not oFolder Is Nothing Then
        SelecionarPasta = oFolder.Self.Path
    End If
End Function
