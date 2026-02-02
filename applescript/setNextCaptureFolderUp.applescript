-- setNextCaptureFolder.applescript
-- Opens next_capture_folder.xml (in the current Capture One session folder),
-- parses it and stores all XML data in variables.

tell application "Capture One"
	set doc to current document
	set sessionPathHFS to path of doc -- Capture One returns an HFS path
	set sessionPathPOSIX to POSIX path of sessionPathHFS
	set TsessionName to name of doc
	set sessionName to text 1 through ((length of TsessionName) - 12) of TsessionName
end tell

-- Build path to the XML file in the session folder
if sessionPathPOSIX does not end with "/" then
	set sessionPathPOSIX to sessionPathPOSIX & "/"
end if
set xmlFilePath to sessionPathPOSIX & sessionName & "/next_capture_folder.xml"

-- Read the XML file
set xmlContent to read (POSIX file xmlFilePath)
set xmlLen to length of xmlContent

-- Helper: extract text between <tagName> and </tagName>
set workingDir to ""
set wdStart to (offset of "<working_dir>" in xmlContent) + (length of "<working_dir>")
set wdEnd to offset of "</working_dir>" in xmlContent
if wdEnd > 0 then set workingDir to text wdStart thru (wdEnd - 1) of xmlContent

set lotFolder to ""
set lfStart to (offset of "<lot_folder>" in xmlContent) + (length of "<lot_folder>")
set lfEnd to offset of "</lot_folder>" in xmlContent
if lfEnd > 0 then set lotFolder to text lfStart thru (lfEnd - 1) of xmlContent

set currentSubfolder to ""
set csStart to (offset of "<current_subfolder>" in xmlContent) + (length of "<current_subfolder>")
set csEnd to offset of "</current_subfolder>" in xmlContent
if csEnd > 0 then set currentSubfolder to text csStart thru (csEnd - 1) of xmlContent

-- All <subfolder>...</subfolder> values into a list
set subfolderList to {}
set searchPos to 1
repeat
	set chunk to text searchPos thru xmlLen of xmlContent
	set subStart to offset of "<subfolder>" in chunk
	if subStart is 0 then exit repeat
	set absSubStart to searchPos + subStart - 1
	set valueStart to absSubStart + (length of "<subfolder>")
	set subEndChunk to text valueStart thru xmlLen of xmlContent
	set subEnd to offset of "</subfolder>" in subEndChunk
	if subEnd is 0 then exit repeat
	set valueEnd to valueStart + subEnd - 2
	set oneSubfolder to text valueStart thru valueEnd of xmlContent
	set subfolderList to subfolderList & {oneSubfolder}
	set searchPos to valueStart + subEnd - 1 + (length of "</subfolder>")
	if searchPos > xmlLen then exit repeat
end repeat

-- Variables now available:
-- workingDir       = full path to working/session directory
-- lotFolder        = name of the lot folder (e.g. 001_LotName)
-- currentSubfolder = current subfolder index (e.g. 1)
-- subfolderList    = list of subfolder names

-- Update current_subfolder: decrement by 1, or wrap to subfolderCount if at first subfolder
set subfolderCount to length of subfolderList
set currentNum to currentSubfolder as number
if currentNum > 1 then
	set newCurrentSubfolder to currentNum - 1
else
	set newCurrentSubfolder to subfolderCount
end if

-- Replace only the numeric value between <current_subfolder> and </current_subfolder> (leave tags and whitespace untouched)
-- Find the ">" that closes the opening tag so valueStart is correct ("current_subfolder>" is 18 chars)
set closingAngleOffset to offset of "current_subfolder>" in xmlContent
set valueStart to closingAngleOffset + 18
set closeTagOffset to offset of "</current_subfolder>" in xmlContent
set valueEnd to closeTagOffset - 1
set beforePart to text 1 thru (valueStart - 1) of xmlContent
set afterPart to text (valueEnd + 1) thru xmlLen of xmlContent
set xmlContent to beforePart & (newCurrentSubfolder as text) & afterPart
set fileRef to open for access (POSIX file xmlFilePath) with write permission
set eof fileRef to 0
write xmlContent to fileRef
close access fileRef
set currentSubfolder to (newCurrentSubfolder as text)

tell application "Capture One"
	
	set doc to current document
	tell doc
		set captures to sessionPathPOSIX & sessionName & "/Capture/" & lotFolder & "/" & item currentSubfolder of subfolderList
	end tell
end tell
