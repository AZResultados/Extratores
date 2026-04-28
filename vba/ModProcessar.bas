Attribute VB_Name = "ModProcessar"
' =============================================================================
' ModProcessar - Botao unico de processamento
' Caminhos via ModConfig
' =============================================================================

Sub Processar()
    Dim baseDir As String
    Dim cliente As String
    cliente = SelecionarCliente(baseDir)
    If cliente = "" Then Exit Sub

    Dim inputDir As String
    inputDir = SelecionarPasta( _
        "Selecione a pasta com os PDFs de " & cliente, baseDir)
    If inputDir = "" Then Exit Sub

    Call ProcessarExtrator(cliente, inputDir)
End Sub
