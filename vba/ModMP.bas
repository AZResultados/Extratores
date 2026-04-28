Attribute VB_Name = "ModMP"
' =============================================================================
' ModMP - Extrator Cartão Mercado Pago
' Para adicionar novo extrator: copie este arquivo, renomeie e ajuste
' celulaScript (Config!B?), celulaInputDir (Config!B?) e nomeExtrator
' =============================================================================

Sub ProcessarMP()
    Dim wsConfig As Worksheet
    Set wsConfig = ThisWorkbook.Sheets("Config")
    Call ProcessarExtrator( _
        "B2", "Mercado Pago", _
        wsConfig.Range("B4").Value, _
        wsConfig.Range("B5").Value)
End Sub
