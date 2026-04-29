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
          " --cliente "   & Chr(34) & EscapeArg(nomeCliente) & Chr(34) & _
          " --input-dir " & Chr(34) & EscapeArg(inputDir)    & Chr(34)

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)

    oExec.StdIn.Close

    jsonStr = Trim(oExec.StdOut.ReadAll)
    errStr  = oExec.StdErr.ReadAll

    If oExec.ExitCode <> 0 Then
        MsgBox "ERRO ao processar " & nomeCliente & ":" & vbCrLf & errStr, vbCritical
        Exit Sub
    End If

    If Len(Trim(errStr)) > 0 Then
        MsgBox "Aviso tecnico:" & vbCrLf & errStr, vbExclamation
    End If

    On Error GoTo ErroParse

    Dim lancamentos As Collection
    Set lancamentos = ParseExtratorJSON(jsonStr)

    On Error Resume Next
    Set wsDados = ThisWorkbook.Sheets("LctosTratados")
    On Error GoTo ErroParse

    If wsDados Is Nothing Then
        ' Primeira execucao: aba ainda nao existe
        Set wsDados = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsDados.Name = "LctosTratados"
        Call CriarCabecalho(wsDados)
    ElseIf wsDados.Cells(1, 1).Value <> "Cliente" Then
        ' Aba existe mas com schema antigo: preserva como legado
        On Error Resume Next
        wsDados.Name = "LctosTratados_legado"
        On Error GoTo ErroParse
        Set wsDados = ThisWorkbook.Sheets.Add( _
            After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        wsDados.Name = "LctosTratados"
        Call CriarCabecalho(wsDados)
    End If

    Dim lastRow    As Long
    Dim rowNum     As Long
    Dim dict       As Object
    Dim dataCompra As Variant

    lastRow = wsDados.Cells(wsDados.Rows.Count, "A").End(xlUp).Row + 1
    rowNum  = lastRow

    For Each dict In lancamentos
        dataCompra = dict("data_compra")
        With wsDados
            .Cells(rowNum,  1).Value = dict("cliente")
            .Cells(rowNum,  2).Value = dict("id_lote")
            .Cells(rowNum,  3).Value = dict("arquivo")
            .Cells(rowNum,  4).Value = dict("titular")
            .Cells(rowNum,  5).Value = dict("final_cartao")
            .Cells(rowNum,  6).Value = dict("tipo")
            If IsDate(dataCompra) Then
                .Cells(rowNum, 7).Value        = dataCompra
                .Cells(rowNum, 7).NumberFormat = "dd/mm/yyyy"
            End If
            .Cells(rowNum,  8).Value = dict("descricao")
            .Cells(rowNum,  9).Value = dict("parcela_num")
            .Cells(rowNum, 10).Value = dict("qtde_parcelas")
            .Cells(rowNum, 11).Value        = dict("vencimento")
            .Cells(rowNum, 11).NumberFormat = "dd/mm/yyyy"
            .Cells(rowNum, 12).Value = dict("descricao_adaptada")
            .Cells(rowNum, 13).Value        = dict("valor")
            .Cells(rowNum, 13).NumberFormat = "#,##0.00"
        End With
        rowNum = rowNum + 1
    Next dict

    MsgBox (rowNum - lastRow) & " lancamentos importados para " & nomeCliente, vbInformation
    wsDados.Activate
    wsDados.Cells(2, 1).Select
    Exit Sub

ErroParse:
    MsgBox "ERRO ao processar " & nomeCliente & ":" & vbCrLf & _
           Err.Description & vbCrLf & vbCrLf & _
           "JSON (200 chars): " & Left(jsonStr, 200), vbCritical
End Sub


' =============================================================================
' Utilitarios compartilhados
' =============================================================================

Function ObterListaClientes() As String()
    Dim vazio(0) As String
    vazio(0) = ""

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec = oShell.Exec("cmd /c chcp 65001 > nul && " & _
                Chr(34) & PythonExe() & Chr(34) & " " & _
                Chr(34) & SetupClienteScript() & Chr(34) & " list")
    oExec.StdIn.Close

    Dim saida As String, erroStr As String
    saida   = Replace(Trim(oExec.StdOut.ReadAll), vbCr, "")
    erroStr = oExec.StdErr.ReadAll

    If oExec.ExitCode <> 0 Then
        MsgBox "ERRO ao listar clientes:" & vbCrLf & erroStr, vbCritical
        ObterListaClientes = vazio
        Exit Function
    End If

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


' =============================================================================
' Parser JSON puro VBA — sem ScriptControl/eval
' Entrada: string JSON de array de objetos
' Chaves tratadas: data, lcto, historico, complemento, debito, credito, saldo, documento
' =============================================================================

Function ParseExtratorJSON(jsonStr As String) As Collection
    Dim result As Collection
    Set result = New Collection

    ' Localiza o array mais externo [ ... ]
    Dim arrStart As Long, arrEnd As Long
    arrStart = InStr(jsonStr, "[")
    arrEnd   = InStrRev(jsonStr, "]")
    If arrStart = 0 Or arrEnd <= arrStart Then
        Set ParseExtratorJSON = result
        Exit Function
    End If

    Dim arrContent As String
    arrContent = Trim(Mid(jsonStr, arrStart + 1, arrEnd - arrStart - 1))
    If Len(arrContent) = 0 Then
        Set ParseExtratorJSON = result   ' array vazio [] — sem erro
        Exit Function
    End If

    ' Percorre char a char para encontrar objetos { } de nivel 1
    Dim depth     As Long
    Dim dentroStr As Boolean
    Dim escaped   As Boolean
    Dim objStart  As Long
    Dim pos       As Long
    Dim c         As String
    Dim d         As Object

    depth     = 0
    dentroStr = False
    escaped   = False
    objStart  = 0

    For pos = 1 To Len(arrContent)
        c = Mid(arrContent, pos, 1)
        If escaped Then
            escaped = False
        ElseIf dentroStr Then
            If c = "\" Then
                escaped = True
            ElseIf c = Chr(34) Then
                dentroStr = False
            End If
        Else
            If c = Chr(34) Then
                dentroStr = True
            ElseIf c = "{" Then
                depth = depth + 1
                If depth = 1 Then objStart = pos
            ElseIf c = "}" Then
                depth = depth - 1
                If depth = 0 And objStart > 0 Then
                    Set d = ParseJSONObject(Mid(arrContent, objStart, pos - objStart + 1))
                    result.Add d
                    objStart = 0
                End If
            End If
        End If
    Next pos

    Set ParseExtratorJSON = result
End Function


Private Function ParseJSONObject(objStr As String) As Object
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")

    Dim pos     As Long
    Dim c       As String
    Dim escaped As Boolean
    Dim isStr   As Boolean
    Dim key     As String
    Dim valStr  As String
    Dim p0      As Long

    pos = 2  ' salta '{'

    Do While pos <= Len(objStr)

        ' Avanca ate abertura de chave (string de chave) ou fim do objeto
        Do While pos <= Len(objStr)
            c = Mid(objStr, pos, 1)
            If c = Chr(34) Then Exit Do
            If c = "}" Then GoTo DoneObj
            pos = pos + 1
        Loop
        If pos > Len(objStr) Then GoTo DoneObj

        ' Le a chave
        pos = pos + 1
        p0 = pos
        escaped = False
        Do While pos <= Len(objStr)
            c = Mid(objStr, pos, 1)
            If escaped Then
                escaped = False
            ElseIf c = "\" Then
                escaped = True
            ElseIf c = Chr(34) Then
                Exit Do
            End If
            pos = pos + 1
        Loop
        key = UnescapeJSON(Mid(objStr, p0, pos - p0))
        pos = pos + 1  ' salta '"' de fechamento

        ' Salta ':' e espacos
        Do While pos <= Len(objStr)
            c = Mid(objStr, pos, 1)
            If c <> ":" And c <> " " And c <> vbTab Then Exit Do
            pos = pos + 1
        Loop
        If pos > Len(objStr) Then GoTo DoneObj

        ' Le o valor
        c = Mid(objStr, pos, 1)
        If c = Chr(34) Then
            ' String JSON
            pos = pos + 1
            p0 = pos
            escaped = False
            Do While pos <= Len(objStr)
                c = Mid(objStr, pos, 1)
                If escaped Then
                    escaped = False
                ElseIf c = "\" Then
                    escaped = True
                ElseIf c = Chr(34) Then
                    Exit Do
                End If
                pos = pos + 1
            Loop
            valStr = UnescapeJSON(Mid(objStr, p0, pos - p0))
            pos = pos + 1
            isStr = True
        ElseIf c = "n" Then
            valStr = "null" : pos = pos + 4 : isStr = False
        ElseIf c = "t" Then
            valStr = "true" : pos = pos + 4 : isStr = False
        ElseIf c = "f" Then
            valStr = "false" : pos = pos + 5 : isStr = False
        Else
            ' Numero
            p0 = pos
            Do While pos <= Len(objStr)
                c = Mid(objStr, pos, 1)
                If c = "," Or c = "}" Or c = " " Or c = vbTab _
                   Or c = vbCr Or c = vbLf Then Exit Do
                pos = pos + 1
            Loop
            valStr = Trim(Mid(objStr, p0, pos - p0))
            isStr = False
        End If

        dict(key) = ConvertJSONValue(key, valStr, isStr)

        ' Avanca apos a virgula separadora
        Do While pos <= Len(objStr)
            c = Mid(objStr, pos, 1)
            If c = "," Then pos = pos + 1 : Exit Do
            If c = "}" Then GoTo DoneObj
            If c = Chr(34) Then Exit Do
            pos = pos + 1
        Loop

    Loop

DoneObj:
    Set ParseJSONObject = dict
End Function


Private Function UnescapeJSON(s As String) As String
    Dim result     As String
    Dim pos        As Long
    Dim c          As String
    Dim hexStr     As String
    Dim codePoint  As Long

    result = ""
    pos    = 1
    Do While pos <= Len(s)
        c = Mid(s, pos, 1)
        If c = "\" And pos < Len(s) Then
            pos = pos + 1
            c = Mid(s, pos, 1)
            Select Case c
                Case Chr(34) : result = result & Chr(34)
                Case "\"     : result = result & "\"
                Case "/"     : result = result & "/"
                Case "n"     : result = result & vbLf
                Case "r"     : result = result & vbCr
                Case "t"     : result = result & vbTab
                Case "u"
                    ' \uXXXX — obrigatorio com ensure_ascii=True no Python
                    If pos + 4 <= Len(s) Then
                        hexStr = Mid(s, pos + 1, 4)
                        On Error Resume Next
                        codePoint = CLng("&H" & hexStr)
                        If Err.Number = 0 Then
                            result = result & ChrW(codePoint)
                        Else
                            result = result & "\u" & hexStr
                        End If
                        On Error GoTo 0
                        pos = pos + 4   ' consome os 4 digitos hex
                    Else
                        result = result & "\u"
                    End If
                Case Else : result = result & "\" & c
            End Select
        Else
            result = result & c
        End If
        pos = pos + 1
    Loop
    UnescapeJSON = result
End Function


Private Function ConvertJSONValue(key As String, sVal As String, isStr As Boolean) As Variant
    Select Case key

        Case "valor"
            ' Val() usa '.' como separador decimal independente de locale
            If sVal = "" Or sVal = "null" Then
                ConvertJSONValue = 0#
            Else
                ConvertJSONValue = Val(sVal)
            End If

        Case "parcela_num", "qtde_parcelas"
            If sVal = "" Or sVal = "null" Then
                ConvertJSONValue = 0
            Else
                On Error Resume Next
                ConvertJSONValue = CLng(sVal)
                If Err.Number <> 0 Then ConvertJSONValue = 0
                On Error GoTo 0
            End If

        Case "data_compra", "vencimento"
            ' Retorna "" para datas nulas; DateSerial para dd/mm/yyyy (locale-safe)
            If sVal = "" Or sVal = "null" Then
                ConvertJSONValue = ""
            ElseIf Len(sVal) = 10 And Mid(sVal, 3, 1) = "/" And Mid(sVal, 6, 1) = "/" Then
                ConvertJSONValue = DateSerial( _
                    CInt(Mid(sVal, 7, 4)), CInt(Mid(sVal, 4, 2)), CInt(Left(sVal, 2)))
            ElseIf Len(sVal) = 10 And Mid(sVal, 5, 1) = "-" And Mid(sVal, 8, 1) = "-" Then
                ConvertJSONValue = DateSerial( _
                    CInt(Left(sVal, 4)), CInt(Mid(sVal, 6, 2)), CInt(Mid(sVal, 9, 2)))
            Else
                On Error Resume Next
                ConvertJSONValue = CDate(sVal)
                If Err.Number <> 0 Then ConvertJSONValue = sVal
                On Error GoTo 0
            End If

        Case Else
            If sVal = "null" Then
                ConvertJSONValue = ""
            Else
                ConvertJSONValue = sVal
            End If

    End Select
End Function


' =============================================================================
' Privados
' =============================================================================

Private Function EscapeArg(s As String) As String
    ' Substitui aspas duplas internas por "" (convencao cmd.exe para strings quoted).
    EscapeArg = Replace(s, Chr(34), Chr(34) & Chr(34))
End Function


Private Sub CriarCabecalho(ws As Worksheet)
    ws.Cells(1,  1).Value = "Cliente"
    ws.Cells(1,  2).Value = "ID_Lote"
    ws.Cells(1,  3).Value = "Arquivo Origem"
    ws.Cells(1,  4).Value = "Titular do Cart" & Chr(227) & "o"
    ws.Cells(1,  5).Value = "Final Cart" & Chr(227) & "o"
    ws.Cells(1,  6).Value = "Tipo"
    ws.Cells(1,  7).Value = "Data da Compra"
    ws.Cells(1,  8).Value = "Descri" & Chr(231) & Chr(227) & "o"
    ws.Cells(1,  9).Value = "Parcela"
    ws.Cells(1, 10).Value = "Qtde Parcelas"
    ws.Cells(1, 11).Value = "Data de Vencimento"
    ws.Cells(1, 12).Value = "Descri" & Chr(231) & Chr(227) & "o Adaptada"
    ws.Cells(1, 13).Value = "Valor (R$)"
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
