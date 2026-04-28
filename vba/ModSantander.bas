Attribute VB_Name = "ModSantander"
' =============================================================================
' ModSantander - Extrator Cartão Santander
' Para adicionar novo extrator: copie este arquivo, renomeie e ajuste
' celulaScript (Config!B?) e nomeExtrator
' =============================================================================

Sub ProcessarSantander()
    Call ProcessarExtrator("B3", "Santander")
End Sub
