#property strict
#property version "1.00"
// Diagnostic transport only. No charts, accounts, trading, timers or external I/O.
void OnStart()
{
   int file=FileOpen("RuntimeTransportProbe.txt",FILE_WRITE|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(file==INVALID_HANDLE) { Print("TRANSPORT_WRITE_FAILED_START"); return; }
   if(FileWriteString(file,"STARTED\n")==0)
   { FileClose(file); Print("TRANSPORT_WRITE_FAILED_START"); return; }
   FileFlush(file);
   Print("TRANSPORT_STARTED");
   string metadata="schema=RUNTIME_TRANSPORT_V1\nscript=RuntimeTransportProbe\nversion=1.00\n"+
      "build="+IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD))+"\n"+
      "data_path="+TerminalInfoString(TERMINAL_DATA_PATH)+"\n";
   if(FileWriteString(file,metadata)==0 || FileWriteString(file,"COMPLETED\n")==0)
   { FileClose(file); Print("TRANSPORT_WRITE_FAILED_COMPLETE"); return; }
   FileFlush(file);
   FileClose(file);
   Print("TRANSPORT_COMPLETED_RETURNING");
}
