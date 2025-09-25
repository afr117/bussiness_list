Read Aloud (Browser Text-to-Speech)



A tiny, single-file webpage (read\_aloud.html) that reads any text out loud using your browser’s built-in Text-to-Speech (Web Speech API). No installs. No server. Works offline in most cases.



Features



Paste or type text and click Speak



Choose a voice available on your device



Adjust Rate (speed) and Pitch



Pause, Resume, and Stop controls



Best in Chrome or Edge on Windows/macOS/Linux.



Quick Start

Windows



Open Notepad and paste the HTML.



File → Save As…



File name: read\_aloud.html



Save as type: All Files (.)



Encoding: UTF-8



Double-click read\_aloud.html to open in your browser.



If it opens in Notepad: it probably saved as read\_aloud.html.txt.

Enable file extensions in Explorer (View → File name extensions) and rename to read\_aloud.html.



macOS



Open TextEdit → Format → Make Plain Text.



Paste the HTML and File → Save…



Save As: read\_aloud.html



If asked, use UTF-8



Open the file in Chrome/Edge.



Linux



Use any editor (e.g., gedit, nano, vim) to save as read\_aloud.html, then open in a browser.



How to Use



Paste your text into the big textbox.



Pick a Voice (wait a moment for the list to populate).



Adjust Rate and Pitch if you like.



Click Speak. Use Pause, Resume, Stop as needed.



Troubleshooting



No sound



Check system volume and that the tab/site isn’t muted.



Headphones/outputs set correctly in OS audio settings.



Voice list is empty



Wait 1–2 seconds; some browsers load voices asynchronously.



Click Speak once, then stop; the list often fills.



Try Chrome/Edge (Firefox support for the Web Speech API is limited).



It speaks but not in my preferred voice



Some platforms expose only a few voices. Choose another from the dropdown.



It works on one machine but not another



Available voices depend on OS/language packs. Installing additional system voices can expand the list.



Privacy



All speech happens locally in your browser. Your text is not uploaded anywhere by this page.



Customization Ideas



Pre-fill the textarea with your own sample text.



Change the default Rate/Pitch values in the HTML.



Add a character counter or an estimated reading time.



Want downloadable audio? The Web Speech API doesn’t provide a clean way to save audio; you’d need a server-side TTS service (SendGrid is for email; for TTS consider providers like Azure/Google/AWS) or I can give you a small Python script to generate MP3s.



File



read\_aloud.html — the entire app in one file.

