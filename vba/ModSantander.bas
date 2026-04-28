Attribute VB_Name = "ModSantander"
' =============================================================================
' ModSantander - Extrator Cartão Santander
' Para adicionar novo extrator: copie este arquivo, renomeie e ajuste
' celulaScript (Config!B?), celulaInputDir (Config!B?) e nomeExtrator
' =============================================================================

Sub ProcessarSantander()
    Dim wsConfig As Worksheet
    Dim wsSenhas As Worksheet
    Set wsConfig = ThisWorkbook.Sheets("Config")
    Set wsSenhas = ThisWorkbook.Sheets("Senhas")
    Call ProcessarExtrator( _
        "B3", "Santander", _
        wsConfig.Range("B4").Value, _
        wsConfig.Range("B6").Value, _
        wsSenhas.Range("B1").Value)
End Sub
