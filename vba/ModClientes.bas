Attribute VB_Name = "ModClientes"
' =============================================================================
' ModClientes - Cadastro de clientes
' Caminhos via ModConfig
' =============================================================================

Sub CadastrarCliente()
    Dim nome As String
    nome = InputBox("Nome do cliente:" & vbCrLf & _
                    "(use exatamente este nome ao cadastrar senhas e processar)", _
                    "Cadastrar Cliente")
    If Trim(nome) = "" Then Exit Sub

    Dim baseDir As String
    baseDir = SelecionarPasta("Selecione a pasta RAIZ do cliente " & nome)
    If baseDir = "" Then Exit Sub

    Dim cmd As String
    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & PythonExe()           & Chr(34) & " " & _
          Chr(34) & SetupClienteScript()  & Chr(34) & _
          " add " & Chr(34) & nome    & Chr(34) & _
          " "     & Chr(34) & baseDir & Chr(34)

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)
    oExec.StdIn.Close

    Dim stdoutStr As String, stderrStr As String
    stdoutStr = oExec.StdOut.ReadAll
    stderrStr = oExec.StdErr.ReadAll

    If oExec.ExitCode = 0 Then
        MsgBox stdoutStr, vbInformation, "Cadastrar Cliente"
    Else
        MsgBox "ERRO: " & stderrStr, vbCritical, "Cadastrar Cliente"
    End If
End Sub


Sub RemoverCliente()
    Dim baseDir As String
    Dim cliente As String
    cliente = SelecionarCliente(baseDir)
    If cliente = "" Then Exit Sub

    If MsgBox("Remover cliente '" & cliente & "'?", _
              vbYesNo + vbQuestion, "Remover Cliente") <> vbYes Then Exit Sub

    Dim cmd As String
    cmd = "cmd /c chcp 65001 > nul && " & _
          Chr(34) & PythonExe()          & Chr(34) & " " & _
          Chr(34) & SetupClienteScript() & Chr(34) & _
          " remove " & Chr(34) & cliente & Chr(34)

    Dim oShell As Object, oExec As Object
    Set oShell = CreateObject("WScript.Shell")
    Set oExec  = oShell.Exec(cmd)
    oExec.StdIn.Close

    Dim stdoutStr As String, stderrStr As String
    stdoutStr = oExec.StdOut.ReadAll
    stderrStr = oExec.StdErr.ReadAll

    If oExec.ExitCode = 0 Then
        MsgBox stdoutStr, vbInformation, "Remover Cliente"
    Else
        MsgBox "ERRO: " & stderrStr, vbCritical, "Remover Cliente"
    End If
End Sub
