from datetime import timedelta

from tests.observer.fixtures import T, frame, position, session, trade
from trading_ecosystem.mt5.client import Record
from trading_ecosystem.observer.context import TIMEFRAMES, build_context, context_key
from trading_ecosystem.observer.contracts import content_id
from trading_ecosystem.observer.replay import replay


def source() -> Record:
    market: dict[str, Record] = {}
    frames = []
    for seq in range(1, 5):
        at = T + timedelta(seconds=seq)
        bars = {
            tf: tuple(
                dict(
                    time=int(T.timestamp()) - i * seconds,
                    open="100",
                    high="101",
                    low="99",
                    close="100",
                )
                for i in range(200, 0, -1)
            )
            for tf, (_, seconds) in TIMEFRAMES.items()
        }
        context, windows = build_context(
            "BTCUSDm", at, dict(time=int(at.timestamp()), bid="100", ask="100.02"), bars, 200
        )
        market.update(windows)
        market[content_id(context)] = context
        frames.append(
            frame(
                seq,
                positions=(position(),)
                if seq == 2
                else ({**position(), "sl": "96"},)
                if seq == 3
                else (),
                deals=(trade(1, 2),)
                if seq == 2
                else (trade(2, 4, type=1, entry=1, profit="10"),)
                if seq == 4
                else (),
                contexts={context_key("BTCUSDm", at): context},
            )
        )
    events, episodes = replay(session(), tuple(frames))
    return dict(
        session=session(),
        frames=tuple(frames),
        events=events,
        episodes=episodes,
        market=market,
        manifest={"created_at": frames[-1].observed_at.isoformat()},
    )
