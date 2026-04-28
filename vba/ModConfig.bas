Attribute VB_Name = "ModConfig"
' =============================================================================
' ModConfig - Caminhos do projeto
' Unica constante a alterar se o projeto mudar de maquina ou pasta: BASE_DIR
' =============================================================================

Private Const BASE_DIR As String = "C:\Dev\projetos\Extratores"

Public Function PythonExe() As String
    PythonExe = BASE_DIR & "\venv\Scripts\python.exe"
End Function

Public Function ExtratorScript() As String
    ExtratorScript = BASE_DIR & "\src\extrator.py"
End Function

Public Function SetupSenhaScript() As String
    SetupSenhaScript = BASE_DIR & "\src\setup_senha.py"
End Function

Public Function SetupClienteScript() As String
    SetupClienteScript = BASE_DIR & "\src\setup_cliente.py"
End Function
