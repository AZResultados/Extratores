Attribute VB_Name = "ModSenhas"
' =============================================================================
' ModSenhas - Cadastro de senhas de PDF
' Senha sempre via stdin — nunca aparece em linha de comando
' Caminhos via ModConfig
' =============================================================================

Sub CadastrarSenhaPDF()
    Dim baseDir As String
    Dim cliente As String
    cliente = SelecionarCliente(baseDir)
    If cliente = "" Then Exit Sub

    Dim senha As String
    senha = InputBox("Senha do PDF para '" & cliente & "':", "Cadastrar Senha PDF")
    If Trim(senha) = "" Then Exit Sub

    Dim cmd As String
    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & PythonExe()         & Chr(34) & " " & _
          Chr(34) & SetupSenhaScript()  & Chr(34) & _
          " add " & Chr(34) & cliente & Chr(34) & " --stdin"

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)

    oExec.StdIn.WriteLine senha
    oExec.StdIn.Close

    If oExec.ExitCode = 0 Then
        MsgBox oExec.StdOut.ReadAll, vbInformation, "Cadastrar Senha PDF"
    Else
        MsgBox "ERRO: " & oExec.StdErr.ReadAll, vbCritical, "Cadastrar Senha PDF"
    End If
End Sub


Sub RemoverSenhaPDF()
    Dim baseDir As String
    Dim cliente As String
    cliente = SelecionarCliente(baseDir)
    If cliente = "" Then Exit Sub

    Dim senha As String
    senha = InputBox("Senha a remover para '" & cliente & "':", "Remover Senha PDF")
    If Trim(senha) = "" Then Exit Sub

    Dim cmd As String
    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & PythonExe()        & Chr(34) & " " & _
          Chr(34) & SetupSenhaScript() & Chr(34) & _
          " remove " & Chr(34) & cliente & Chr(34) & " --stdin"

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)

    oExec.StdIn.WriteLine senha
    oExec.StdIn.Close

    MsgBox oExec.StdOut.ReadAll, vbInformation, "Remover Senha PDF"
End Sub
