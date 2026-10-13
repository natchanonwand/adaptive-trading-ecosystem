#property strict
#property version "1.00"
#property description "Project-owned tester-only pipeline reference; not a production strategy"

input int InpFastEmaPeriod = 20;
input int InpSlowEmaPeriod = 100;

const ulong REFERENCE_MAGIC = 52020001;
const double FIXED_LOTS = 0.01;
int fast_handle = INVALID_HANDLE;
int slow_handle = INVALID_HANDLE;
datetime evaluated_bar = 0;

bool TesterOnly()
{
   return MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_OPTIMIZATION)
          && AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO;
}

int OnInit()
{
   if(!TesterOnly() || _Period != PERIOD_M5)
   {
      Print("REFERENCE_REJECTED: DEMO M5 tester only; optimizer prohibited");
      return INIT_FAILED;
   }
   if(InpFastEmaPeriod <= 0 || InpSlowEmaPeriod <= 0
      || InpFastEmaPeriod >= InpSlowEmaPeriod)
   {
      Print("REFERENCE_INVALID_EMA_PERIODS");
      return INIT_PARAMETERS_INCORRECT;
   }
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0 || FIXED_LOTS < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)
      || FIXED_LOTS > SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX)
      || MathAbs(FIXED_LOTS / step - MathRound(FIXED_LOTS / step)) > 1e-8)
   {
      Print("REFERENCE_FIXED_VOLUME_UNSUPPORTED");
      return INIT_FAILED;
   }
   fast_handle = iMA(_Symbol, PERIOD_M5, InpFastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   slow_handle = iMA(_Symbol, PERIOD_M5, InpSlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(fast_handle == INVALID_HANDLE || slow_handle == INVALID_HANDLE)
      return INIT_FAILED;
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(fast_handle != INVALID_HANDLE) IndicatorRelease(fast_handle);
   if(slow_handle != INVALID_HANDLE) IndicatorRelease(slow_handle);
}

bool Deal(const ENUM_ORDER_TYPE side, const double volume, const ulong ticket)
{
   if(!TesterOnly()) return false;
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return false;
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.magic = REFERENCE_MAGIC;
   request.volume = volume;
   request.type = side;
   request.position = ticket;
   request.price = side == ORDER_TYPE_BUY ? tick.ask : tick.bid;
   request.deviation = 20;
   request.comment = "Project reference EMA";
   long filling = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((filling & SYMBOL_FILLING_FOK) != 0) request.type_filling = ORDER_FILLING_FOK;
   else if((filling & SYMBOL_FILLING_IOC) != 0) request.type_filling = ORDER_FILLING_IOC;
   else return false;
   if(!OrderSend(request, result) || result.retcode != TRADE_RETCODE_DONE)
   {
      PrintFormat("REFERENCE_DEAL_FAILED: %u", result.retcode);
      return false; // No retries, including partial fills.
   }
   return true;
}

void OnTick()
{
   if(!TesterOnly()) { ExpertRemove(); return; }
   datetime bar = iTime(_Symbol, PERIOD_M5, 0);
   if(bar == 0 || bar == evaluated_bar) return;
   if(BarsCalculated(fast_handle) < InpSlowEmaPeriod + 2
      || BarsCalculated(slow_handle) < InpSlowEmaPeriod + 2) return;
   double fast[2], slow[2];
   // Physical order is oldest first: [0] = closed bar 2, [1] = closed bar 1.
   if(CopyBuffer(fast_handle, 0, 1, 2, fast) != 2
      || CopyBuffer(slow_handle, 0, 1, 2, slow) != 2) return;
   evaluated_bar = bar;
   int direction = 0;
   if(fast[1] > slow[1] && fast[0] <= slow[0]) direction = 1;
   if(fast[1] < slow[1] && fast[0] >= slow[0]) direction = -1;
   if(direction == 0) return;
   ulong owned = 0;
   for(int index = PositionsTotal() - 1; index >= 0; index--)
   {
      ulong ticket = PositionGetTicket(index);
      if(ticket == 0) { ExpertRemove(); return; }
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if((ulong)PositionGetInteger(POSITION_MAGIC) != REFERENCE_MAGIC || owned != 0)
      {
         Print("REFERENCE_POSITION_ISOLATION_FAILED");
         ExpertRemove();
         return;
      }
      owned = ticket;
   }
   if(owned != 0)
   {
      if(!PositionSelectByTicket(owned)) { ExpertRemove(); return; }
      bool is_long = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      if((direction == 1) == is_long) return;
      double volume = PositionGetDouble(POSITION_VOLUME);
      if(!Deal(is_long ? ORDER_TYPE_SELL : ORDER_TYPE_BUY, volume, owned)
         || PositionSelectByTicket(owned)) { ExpertRemove(); return; }
   }
   if(!Deal(direction == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, FIXED_LOTS, 0))
      ExpertRemove();
}
