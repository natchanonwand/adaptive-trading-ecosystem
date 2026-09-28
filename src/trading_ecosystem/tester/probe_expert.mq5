#property strict
#property version "1.00"

bool first_tick_seen = false;

int OnInit()
{
   if(!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return INIT_FAILED;
   Print("PHASE5B_PROBE_INIT_OK");
   return INIT_SUCCEEDED;
}

void OnTick()
{
   if(first_tick_seen)
      return;
   first_tick_seen = true;
   Print("PHASE5B_PROBE_FIRST_TICK");
   TesterStop();
}

void OnDeinit(const int reason)
{
   PrintFormat("PHASE5B_PROBE_DEINIT:%d", reason);
}
