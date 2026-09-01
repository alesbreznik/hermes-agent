Local AI Writing Assistant
==========================

Overview
--------
This tool provides AI-assisted text completion, rewriting, and content enhancement directly in any Windows application.
It automatically installs key bindings via AutoHotkey, Ollama and Qwen1.5:2b model to run locally and autostarts on system startup.
The script is designed to run on laptop hardware and favors GPU execution, that usually remains dormant and unused, if available, otherwise it runs fine in RAM. 

It combines:
- AI autocomplete similar to GitHub Copilot
- Grammar and wording improvement similar to Grammarly
- Business writing enhancement for emails, documents, presentations, tickets, chats, and reports

The assistant runs entirely on your local machine using Ollama and a local language model.
No cloud services or external APIs are required once installed.


Typical Use Cases
-----------------
- Improve rough notes or handwritten text
- Expand slide bullet points into complete statements
- Rewrite and polish emails
- Complete unfinished thoughts
- Improve wording and clarity
- Add business value, outcomes, benefits, or context
- Draft executive summaries
- Enhance project documentation
- Improve reports, tickets, and meeting notes

Operation
-------

CTRL + SPACE:
    Generate a SHORT suggestion.
	If no text is selected the model will attempt to grab context behind the cursor and insert it after the cursor.
	If text is selected the model will grab the selected text as context and rewrite it if suggestion is accepted.
   
CTRL + SHIFT + SPACE
    Generate a SHORT suggestion.
	Provides the same functionality as SHORT suggestion, but adds more prediction text and provides longer suggestions. 

CTRL + TAB
	Accept the suggestion that appears in the popup.
	If text is selected it will overwrite.
	If no text is selected it will add where the writing cursor is. 

ESC
	Decline suggestion and close popup.


NOTE: It is possible to continue to write and move the writing cursor indicator after the popup appears and specify where the text should be inserted.


Examples
--------

Input:
Materal folw control - dinamyc multi site end to end product lineag

Short Mode Output: Ctrl + Space
Material flow control – Dynamic, multi-site end-to-end product lineage enabling full traceability across manufacturing operations.

Long Mode Output: Ctrl + Shift + Space
Material flow control – Dynamic, multi-site end-to-end product lineage enabling full traceability, genealogy tracking, and real-time visibility across manufacturing operations and business processes.


