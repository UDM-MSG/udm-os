# tools/gen_secret.ps1 - Prints a 64-char hex (256-bit) secret to STDOUT
$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
