@echo off
setlocal EnableExtensions DisableDelayedExpansion

title Local AI Text Assistant Installer

set "APPNAME=OllamaAutocomplete"
set "INSTALLDIR=%LOCALAPPDATA%\%APPNAME%"
set "AHKSCRIPT=%INSTALLDIR%\autocomplete.ahk"
set "MODEL=qwen2.5-coder:1.5b"

echo.
echo ============================================================
echo  Local AI Text Assistant Installer
echo ============================================================
echo.

echo [1/10] Creating install directory...
if not exist "%INSTALLDIR%" mkdir "%INSTALLDIR%"

echo.
echo [2/10] Checking winget...
where winget >nul 2>nul
if errorlevel 1 (
    echo ERROR: winget was not found.
    echo.
    echo Please install/enable App Installer or ask IT to enable winget.
    pause
    exit /b 1
)

echo.
echo [3/10] Checking AutoHotkey...
call :FindAutoHotkey

if defined AHK_EXE (
    echo AutoHotkey already found:
    echo   %AHK_EXE%
) else (
    echo AutoHotkey not found. Installing AutoHotkey v2...
    winget install --id AutoHotkey.AutoHotkey --exact --silent --accept-package-agreements --accept-source-agreements

    call :FindAutoHotkey

    if not defined AHK_EXE (
        echo ERROR: AutoHotkey installation completed, but AutoHotkey executable was not found.
        pause
        exit /b 1
    )

    echo AutoHotkey installed:
    echo   %AHK_EXE%
)

echo.
echo [4/10] Checking Ollama...
call :FindOllama

if defined OLLAMA_EXE (
    echo Ollama already found:
    echo   %OLLAMA_EXE%
) else (
    echo Ollama not found. Installing Ollama...
    winget install --id Ollama.Ollama --exact --silent --accept-package-agreements --accept-source-agreements

    call :FindOllama

    if not defined OLLAMA_EXE (
        echo ERROR: Ollama installation completed, but ollama.exe was not found.
        echo Try opening a new terminal and running: ollama --version
        pause
        exit /b 1
    )

    echo Ollama installed:
    echo   %OLLAMA_EXE%
)

echo.
echo [5/10] Setting Ollama environment variables if missing...
call :EnsureUserEnv OLLAMA_CONTEXT_LENGTH 1024
call :EnsureUserEnv OLLAMA_KEEP_ALIVE 12h
call :EnsureUserEnv OLLAMA_NUM_PARALLEL 1
call :EnsureUserEnv OLLAMA_MAX_LOADED_MODELS 1
call :EnsureUserEnv OLLAMA_GPU_OVERHEAD 0

echo.
echo Active values for this setup run:
echo   OLLAMA_CONTEXT_LENGTH=%OLLAMA_CONTEXT_LENGTH%
echo   OLLAMA_KEEP_ALIVE=%OLLAMA_KEEP_ALIVE%
echo   OLLAMA_NUM_PARALLEL=%OLLAMA_NUM_PARALLEL%
echo   OLLAMA_MAX_LOADED_MODELS=%OLLAMA_MAX_LOADED_MODELS%
echo   OLLAMA_GPU_OVERHEAD=%OLLAMA_GPU_OVERHEAD%

echo.
echo [6/10] Writing AutoHotkey script...
call :WriteAhkScript

echo.
echo [7/10] Restarting Ollama so settings are active...

taskkill /IM ollama.exe /F >nul 2>nul
timeout /t 3 /nobreak >nul

call :FindOllama

if not defined OLLAMA_EXE (
    echo ERROR: Could not find ollama.exe.
    pause
    exit /b 1
)

echo Starting Ollama:
echo   %OLLAMA_EXE%

start "Ollama Serve" /MIN "%OLLAMA_EXE%" serve

echo Waiting for Ollama API...
set /a WAITCOUNT=0

:WaitOllama
curl -s http://localhost:11434/api/tags >nul 2>nul
if not errorlevel 1 goto OllamaReady

set /a WAITCOUNT+=1
if %WAITCOUNT% GEQ 45 (
    echo ERROR: Ollama API did not become available at http://localhost:11434
    pause
    exit /b 1
)

timeout /t 2 /nobreak >nul
goto WaitOllama

:OllamaReady
echo Ollama API is ready.

echo.
echo [8/10] Pulling/verifying model: %MODEL%
echo If the model already exists, Ollama should verify it quickly.
"%OLLAMA_EXE%" pull %MODEL%

if errorlevel 1 (
    echo ERROR: Model pull failed.
    echo Check network access, proxy/VPN, or company firewall rules.
    pause
    exit /b 1
)

echo.
echo Warming model and keeping it loaded...
curl -s -X POST http://localhost:11434/api/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"%MODEL%\",\"prompt\":\"Ready.\",\"stream\":false,\"keep_alive\":\"12h\",\"options\":{\"num_ctx\":1024,\"num_predict\":4,\"temperature\":0.1,\"num_gpu\":999}}" >nul 2>nul

echo.
echo [9/10] Creating Startup shortcut...

call :CreateStartupShortcut

if errorlevel 1 (
    echo ERROR: Could not create Startup shortcut.
    pause
    exit /b 1
)

echo Startup shortcut created or updated.

echo.
echo [10/10] Starting AutoHotkey script...

taskkill /IM AutoHotkey64.exe /F >nul 2>nul
taskkill /IM AutoHotkey.exe /F >nul 2>nul

start "Ollama Autocomplete" "%AHK_EXE%" "%AHKSCRIPT%"

echo.
echo ============================================================
echo  Installation complete.
echo ============================================================
echo.
echo Usage:
echo   CTRL + SPACE  = generate suggestion
echo   CTRL + TAB    = accept suggestion
echo   ESC           = cancel suggestion
echo.
echo Installed script:
echo   %AHKSCRIPT%
echo.
echo Model:
echo   %MODEL%
echo.
pause
exit /b 0


:FindOllama
set "OLLAMA_EXE="

where ollama.exe > "%TEMP%\ollama_where.txt" 2>nul
for /f "usebackq delims=" %%A in ("%TEMP%\ollama_where.txt") do (
    if not defined OLLAMA_EXE set "OLLAMA_EXE=%%A"
)

if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"

exit /b 0


:FindAutoHotkey
set "AHK_EXE="

if exist "%ProgramFiles%\AutoHotkey\v2\AutoHotkey64.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\v2\AutoHotkey64.exe"
if not defined AHK_EXE if exist "%ProgramFiles%\AutoHotkey\AutoHotkey.exe" set "AHK_EXE=%ProgramFiles%\AutoHotkey\AutoHotkey.exe"
if not defined AHK_EXE if exist "%LOCALAPPDATA%\Programs\AutoHotkey\v2\AutoHotkey64.exe" set "AHK_EXE=%LOCALAPPDATA%\Programs\AutoHotkey\v2\AutoHotkey64.exe"
if not defined AHK_EXE if exist "%LOCALAPPDATA%\Programs\AutoHotkey\AutoHotkey.exe" set "AHK_EXE=%LOCALAPPDATA%\Programs\AutoHotkey\AutoHotkey.exe"

if not defined AHK_EXE (
    where AutoHotkey64.exe > "%TEMP%\ahk_where.txt" 2>nul
    for /f "usebackq delims=" %%A in ("%TEMP%\ahk_where.txt") do (
        if not defined AHK_EXE set "AHK_EXE=%%A"
    )
)

if not defined AHK_EXE (
    where AutoHotkey.exe > "%TEMP%\ahk_where2.txt" 2>nul
    for /f "usebackq delims=" %%A in ("%TEMP%\ahk_where2.txt") do (
        if not defined AHK_EXE set "AHK_EXE=%%A"
    )
)

exit /b 0


:EnsureUserEnv
set "ENVNAME=%~1"
set "DEFAULTVALUE=%~2"

reg query HKCU\Environment /v "%ENVNAME%" >nul 2>nul

if errorlevel 1 (
    echo Setting %ENVNAME%=%DEFAULTVALUE%
    setx "%ENVNAME%" "%DEFAULTVALUE%" >nul
    set "%ENVNAME%=%DEFAULTVALUE%"
) else (
    for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v "%ENVNAME%" 2^>nul ^| find /i "%ENVNAME%"') do (
        set "%ENVNAME%=%%B"
    )
    echo Keeping existing %ENVNAME% value.
)

exit /b 0


:WriteAhkScript
set "EXTRACTVBS=%TEMP%\extract_embedded_ahk.vbs"

> "%EXTRACTVBS%" echo sourceFile = WScript.Arguments(0)
>>"%EXTRACTVBS%" echo targetFile = WScript.Arguments(1)
>>"%EXTRACTVBS%" echo marker = "###BEGIN_AHK_SCRIPT###"
>>"%EXTRACTVBS%" echo Set fso = CreateObject("Scripting.FileSystemObject")
>>"%EXTRACTVBS%" echo Set input = fso.OpenTextFile(sourceFile, 1, False)
>>"%EXTRACTVBS%" echo Set output = fso.OpenTextFile(targetFile, 2, True)
>>"%EXTRACTVBS%" echo found = False
>>"%EXTRACTVBS%" echo Do Until input.AtEndOfStream
>>"%EXTRACTVBS%" echo     line = input.ReadLine
>>"%EXTRACTVBS%" echo     If found Then
>>"%EXTRACTVBS%" echo         output.WriteLine line
>>"%EXTRACTVBS%" echo     ElseIf line = marker Then
>>"%EXTRACTVBS%" echo         found = True
>>"%EXTRACTVBS%" echo     End If
>>"%EXTRACTVBS%" echo Loop
>>"%EXTRACTVBS%" echo input.Close
>>"%EXTRACTVBS%" echo output.Close
>>"%EXTRACTVBS%" echo If Not found Then WScript.Quit 1

cscript //nologo "%EXTRACTVBS%" "%~f0" "%AHKSCRIPT%"

if errorlevel 1 (
    echo ERROR: Could not extract embedded AutoHotkey script.
    del "%EXTRACTVBS%" >nul 2>nul
    exit /b 1
)

del "%EXTRACTVBS%" >nul 2>nul

echo Script written to:
echo   %AHKSCRIPT%

exit /b 0


:CreateStartupShortcut
set "VBS=%TEMP%\create_ollama_autocomplete_shortcut.vbs"

> "%VBS%" echo Set WshShell = WScript.CreateObject("WScript.Shell")
>>"%VBS%" echo StartupFolder = WshShell.SpecialFolders("Startup")
>>"%VBS%" echo Set Shortcut = WshShell.CreateShortcut(StartupFolder ^& "\Ollama Autocomplete.lnk")
>>"%VBS%" echo Shortcut.TargetPath = "%AHK_EXE%"
>>"%VBS%" echo Shortcut.Arguments = Chr(34) ^& "%AHKSCRIPT%" ^& Chr(34)
>>"%VBS%" echo Shortcut.WorkingDirectory = "%INSTALLDIR%"
>>"%VBS%" echo Shortcut.Description = "Ollama Autocomplete Hotkey Script"
>>"%VBS%" echo Shortcut.Save

cscript //nologo "%VBS%" >nul

if errorlevel 1 (
    del "%VBS%" >nul 2>nul
    exit /b 1
)

del "%VBS%" >nul 2>nul
exit /b 0


###BEGIN_AHK_SCRIPT###
#Requires AutoHotkey v2.0

global Suggestion := ""
global OllamaModel := "qwen2.5-coder:1.5b"

; CTRL + SPACE = short cleanup / autocomplete
^Space::
{
    GenerateSuggestion("short")
}

; CTRL + SHIFT + SPACE = longer rewrite / expand
^+Space::
{
    GenerateSuggestion("long")
}

GenerateSuggestion(Mode)
{
    global Suggestion
    global OllamaModel

    Context := GetSelectedTextOrPreviousWord()

    if (Trim(Context) = "")
    {
        MsgBox "No selected text or previous word found."
        return
    }

    if (Mode = "short")
    {
        PromptText :=
        (
"You are an AI autocomplete and text improvement assistant.

Task:
- Fix spelling and grammar.
- Improve wording where beneficial.
- Complete unfinished thoughts.
- Continue the text naturally.

Rules:
- Preserve the original meaning.
- Keep the result concise.
- Add only the minimum content needed to complete the thought.
- Do not create new topics.
- Do not over-explain.
- Output only the final improved text.

Text:
" Context
        )

        NumPredict := 45
        Temperature := 0.25
        ModeLabel := "SHORT"
    }
    else
    {
        PromptText :=
        (
"You are a writing assistant.

Task:
- Rewrite more clearly.
- Expand with additional details.
- Extend the text with useful, relevant context.
- Continue the text naturally with additional information.

Rules:
- Preserve the original meaning.
- Expand the text further with additional 1-2 sentences.
- Keep the result short, dense, clear, and concise.
- Do not create unrelated new topics.
- No explanations.
- No bullet points.
- Output only the final improved text.

Text:
" Context
        )

        NumPredict := 120
        Temperature := 0.50
        ModeLabel := "LONG"
    }

    JsonBody := "{"
        . "`"model`":`"" JsonEscape(OllamaModel) "`","
        . "`"prompt`":`"" JsonEscape(PromptText) "`","
        . "`"stream`":false,"
        . "`"keep_alive`":`"12h`","
        . "`"options`":{"
            . "`"num_ctx`":1024,"
            . "`"num_predict`":" NumPredict ","
            . "`"temperature`":" Temperature ","
            . "`"top_p`":0.95,"
            . "`"repeat_penalty`":1.10,"
            . "`"num_gpu`":999"
        . "}"
    . "}"

    try
    {
        Http := ComObject("WinHttp.WinHttpRequest.5.1")
        Http.Open("POST", "http://localhost:11434/api/generate", false)
        Http.SetRequestHeader("Content-Type", "application/json")
        Http.Send(JsonBody)

        ResponseJson := Http.ResponseText
    }
    catch Error as e
    {
        MsgBox "Failed to contact Ollama.`n`nCheck that Ollama is running at:`nhttp://localhost:11434`n`nError:`n" e.Message
        return
    }

    if RegExMatch(ResponseJson, "`"response`"\s*:\s*`"((?:\\.|[^`"\\])*)`"", &Match)
    {
        Suggestion := JsonUnescape(Match[1])

        ; Clean multiline output into one compact paragraph.
        Suggestion := StrReplace(Suggestion, "`r", " ")
        Suggestion := StrReplace(Suggestion, "`n", " ")
        Suggestion := RegExReplace(Suggestion, "\s+", " ")
        Suggestion := Trim(Suggestion)

        if (Suggestion = "")
        {
            MsgBox "Ollama returned an empty suggestion."
            return
        }

        Preview := Suggestion
        if (StrLen(Preview) > 350)
            Preview := SubStr(Preview, 1, 350) . "..."

        ToolTip ModeLabel " suggestion ready.`nPress CTRL + TAB to accept, ESC to cancel:`n`n" Preview
        SetTimer ClearToolTip, -300000
    }
    else
    {
        MsgBox "Could not parse Ollama response:`n`n" ResponseJson
    }
}

$^Tab::
{
    global Suggestion

    if (Suggestion != "")
    {
        ToolTip

        Send "{Ctrl up}"
        Send "{Shift up}"
        Send "{Alt up}"
        Sleep 50

        SendText Suggestion

        Suggestion := ""
        return
    }

    Send "{Tab}"
}

$^Esc::
{
    global Suggestion

    Suggestion := ""
    ToolTip
}

GetSelectedTextOrPreviousWord()
{
    SavedClip := ClipboardAll()

    ; Try copying selected text first.
    A_Clipboard := ""
    Send "^c"

    SelectedText := ""

    if ClipWait(0.4)
        SelectedText := A_Clipboard

    if (Trim(SelectedText) != "")
    {
        A_Clipboard := SavedClip

        ; Keep selection active so accepting replaces the selected text.
        return SelectedText
    }

    ; No selected text.
    ; Select previous word using keyboard instead of mouse triple-click.
    A_Clipboard := ""
    Send "^+{Left}"
    Sleep 80
    Send "^c"

    PreviousWord := ""

    if ClipWait(0.4)
        PreviousWord := A_Clipboard

    A_Clipboard := SavedClip

    ; Move caret back to the end of the selected previous word.
    Send "{Right}"

    return PreviousWord
}

ClearToolTip()
{
    ToolTip
}

JsonEscape(Text)
{
    Text := StrReplace(Text, "\", "\\")
    Text := StrReplace(Text, '"', '\"')
    Text := StrReplace(Text, "`r", "\r")
    Text := StrReplace(Text, "`n", "\n")
    Text := StrReplace(Text, "`t", "\t")
    return Text
}

JsonUnescape(Text)
{
    Text := StrReplace(Text, "\n", "`n")
    Text := StrReplace(Text, "\r", "`r")
    Text := StrReplace(Text, "\t", "`t")
    Text := StrReplace(Text, '\"', '"')
    Text := StrReplace(Text, "\\", "\")
    return Text
}