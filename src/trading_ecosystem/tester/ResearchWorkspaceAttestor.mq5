#property strict
// Read-only diagnostic: no trading, chart mutation, network or DLL operations.
string Quote(string value)
{
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r","\\r");
   StringReplace(value,"\n","\\n");
   StringReplace(value,"\t","\\t");
   return "\""+value+"\"";
}
void OnStart()
{
   // Allow the independent read-only SDK observer to bind this owned DEMO session.
   for(int i=0;i<15 && !IsStopped();i++) Sleep(1000);
   string rows="";
   int count=0;
   bool valid=true;
   for(long chart=ChartFirst();chart!=-1;chart=ChartNext(chart))
   {
      if(count>=100) { valid=false; break; }
      string expert,script;
      if(!ChartGetString(chart,CHART_EXPERT_NAME,expert) ||
         !ChartGetString(chart,CHART_SCRIPT_NAME,script)) { valid=false; break; }
      if(count>0) rows+=",";
      rows+="{\"ordinal\":"+IntegerToString(count)+",\"symbol\":"+Quote(ChartSymbol(chart))+
            ",\"period\":"+IntegerToString((int)ChartPeriod(chart))+
            ",\"expert_name\":"+Quote(expert)+",\"script_name\":"+Quote(script)+
            ",\"host\":"+(chart==ChartID()?"true":"false")+"}";
      count++;
   }
   string output="{\"schema\":\"RUNTIME_WORKSPACE_V1\",\"valid\":"+(valid?"true":"false")+
      ",\"build\":"+IntegerToString((int)TerminalInfoInteger(TERMINAL_BUILD))+
      ",\"terminal_path\":"+Quote(TerminalInfoString(TERMINAL_PATH))+
      ",\"data_path\":"+Quote(TerminalInfoString(TERMINAL_DATA_PATH))+
      ",\"connected\":"+(TerminalInfoInteger(TERMINAL_CONNECTED)?"true":"false")+
      ",\"account_trade_mode\":"+IntegerToString((int)AccountInfoInteger(ACCOUNT_TRADE_MODE))+
      ",\"account_server\":"+Quote(AccountInfoString(ACCOUNT_SERVER))+
      ",\"charts\":["+rows+"]}";
   int file=FileOpen("ResearchWorkspaceAttestor.json",FILE_WRITE|FILE_TXT|FILE_ANSI,0,CP_UTF8);
   if(file==INVALID_HANDLE) { Print("WORKSPACE_ATTESTATION_OUTPUT_FAILED"); return; }
   FileWriteString(file,output);
   FileFlush(file);
   FileClose(file);
   Print("WORKSPACE_ATTESTATION_COMPLETE");
}
