Attribute VB_Name = "ModMP"
' =============================================================================
' ModMP - Extrator Cartão Mercado Pago
' Para adicionar novo extrator: copie este arquivo, renomeie e ajuste
' celulaScript (Config!B?) e nomeExtrator
' =============================================================================

Sub ProcessarMP()
    Call ProcessarExtrator("B2", "Mercado Pago")
End Sub
