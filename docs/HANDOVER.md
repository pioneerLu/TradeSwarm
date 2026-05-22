# TradeSwarm 椤圭洰浜ゆ帴鏂囨。

> **鍒涘缓鏃ユ湡**: 2026-02-10  
> **椤圭洰鐘舵€?*: 鏍稿績鍔熻兘宸插畬鎴愶紝鍙繘琛屽崟鏍囩殑鍜屽鏍囩殑鍥炴祴  
> **鏈€鍚庡洖娴?*: NVDA 涓冩棩绐楀彛 (2026-02-04 鑷?2026-02-12)锛屼娇鐢?memory.db 棰勭疆鎶ュ憡 + Silicon Flow LLM  
> **鏈€鍚庢洿鏂?*: 2026-02-20

---

## 涓€銆侀」鐩杩?
### 1.1 椤圭洰鐩爣

TradeSwarm 鏄竴涓熀浜庡鏅鸿兘浣擄紙Multi-Agent锛夋灦鏋勭殑 A 鑲″競鍦轰氦鏄撳喅绛栫郴缁燂紝閫氳繃澶氭櫤鑳戒綋鍗忎綔瀹炵幇鏅鸿兘鎶曡祫鍒嗘瀽鍜屽喅绛栥€傜郴缁熼噰鐢?LangGraph 妗嗘灦鏋勫缓锛屾敮鎸佸绉嶆暟鎹簮鎺ュ叆锛屽疄鐜颁簡妯″潡鍖栥€佸彲鎵╁睍鐨勬櫤鑳戒氦鏄撳垎鏋愬钩鍙般€?
**鏍稿績璁捐鐩爣**锛?- 鍙繛缁嚜娌昏繍琛屾暟鍛?鏈?- 澶氭櫤鑳戒綋鍗忎綔鑳藉姏
- 闀挎湡璁板繂涓庤嚜鎴戠ǔ瀹氭満鍒?- 瀹屾暣鐨勫洖娴嬬郴缁?
### 1.2 鎶€鏈爤

- **Python 3.12+**
- **LangChain 1.2.0** + **LangGraph 1.2.0**锛氬伐浣滄祦缂栨帓
- **SQLite** (`memory.db`) + **ChromaDB**锛氭暟鎹寔涔呭寲
- **yfinance** + **Alpha Vantage**锛氭暟鎹簮
- **Jinja2**锛歅rompt 妯℃澘鍖?
### 1.3 褰撳墠鐘舵€?
鉁?**宸插畬鎴愮殑鏍稿績鍔熻兘**锛?- 瀹屾暣鐨?Pre-Open 鍐崇瓥鍥撅紙Summary 鈫?Research 鈫?Risk 鈫?Strategy 鈫?Trader锛?- 鍗曟爣鐨勩€佸鏃ュ洖娴嬮┍鍔ㄥ櫒
- 澶氭爣鐨勩€佸鍛ㄦ湡鍥炴祴鑴氭湰
- 姣忔棩浜ゆ槗鎽樿璁板綍锛坄daily_trading_summaries`锛?- 鍛ㄦ湡绾у弽鎬濅唬鐞嗭紙Reflector Agent锛?- 澶氬洜瀛愰€夎偂涓庡啀骞宠　
- 7 鏃ユ粴鍔ㄥ巻鍙叉憳瑕佺淮鎶?
鈿狅笍 **宸茬煡闂**锛?- Alpha Vantage API 鏈夎闂檺鍒讹紙5 娆?鍒嗛挓锛?00 娆?澶╋級
- Market Open 鎵ц閫昏緫鍦ㄦ煇浜涙儏鍐典笅鍙兘涓嶆墽琛屼氦鏄擄紙闇€瑕佽皟璇曪級
- 閮ㄥ垎鍒嗘瀽甯堣妭鐐瑰湪 API 闄愬埗涓嬪彲鑳藉け璐?
---

## 浜屻€佺郴缁熸灦鏋?
### 2.1 瀹屾暣浜ゆ槗娴佺▼锛堟棩绾э級

```text
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? Pre-Open 鍒嗘瀽  鈹? 鈫?杩愯瀹屾暣鍐崇瓥鍥撅紙Summary 鈫?Research 鈫?Risk 鈫?Strategy 鈫?Trader锛?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹?         鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? Market Open    鈹? 鈫?鎵ц浜ゆ槗锛堟瘡澶╂渶澶氫竴娆★級
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹?         鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? Post Close     鈹? 鈫?鏇存柊浠撲綅銆佽绠楁敹鐩娿€佷繚瀛?daily_summary
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹?         鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?History Maintain鈹? 鈫?鏇存柊 7 鏃ユ粴鍔ㄦ憳瑕?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

### 2.2 Pre-Open 鍐崇瓥鍥剧粨鏋?
```text
Summary 鑺傜偣锛堜覆琛岋級
  鈹溾攢 market_summary
  鈹溾攢 news_summary
  鈹溾攢 sentiment_summary
  鈹斺攢 fundamentals_summary
         鈹?         鈻?Research 瀛愬浘锛? 杞京璁猴級
  鈹溾攢 Bull Researcher (Round 1)
  鈹溾攢 Bear Researcher (Round 1)
  鈹溾攢 Bull Researcher (Round 2)
  鈹溾攢 Bear Researcher (Round 2)
  鈹斺攢 Research Manager
         鈹?         鈻?Risk 瀛愬浘锛? 杞京璁猴級
  鈹溾攢 Aggressive Debator (Round 1)
  鈹溾攢 Neutral Debator (Round 1)
  鈹溾攢 Conservative Debator (Round 1)
  鈹溾攢 Aggressive Debator (Round 2)
  鈹溾攢 Neutral Debator (Round 2)
  鈹溾攢 Conservative Debator (Round 2)
  鈹斺攢 Risk Manager
         鈹?         鈻?Strategy Selector
  鈹斺攢 甯傚満鐘舵€佸垽鏂?+ 绛栫暐閫夋嫨
         鈹?         鈻?Trader
  鈹斺攢 浜ゆ槗鏂瑰悜 + 姝㈢泩姝㈡崯
```

### 2.3 鍛ㄦ湡绾ф祦绋嬶紙鍛?鏈堬級

```text
鍛ㄦ湡寮€濮?    鈹?    鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? 閫夎偂涓庡啀骞宠　    鈹? 鈫?StockSelector 閫夎偂 + PortfolioManager 璋冧粨
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹?         鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? 姣忔棩浜ゆ槗寰幆    鈹? 鈫?瀵规瘡涓€変腑鏍囩殑鎵ц Pre-Open 鈫?Market Open 鈫?Post Close
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?         鈹?         鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹? Reflector      鈹? 鈫?鍛ㄦ湡缁撴潫锛氭€荤粨閿欒妯″紡銆佹垚鍔熸ā寮忋€佺瓥鐣ラ€傜敤鏉′欢
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

### 2.4 鍏抽敭缁勪欢璇存槑

#### Analyst锛堝垎鏋愬笀锛?- **璁捐鍘熷垯**锛氬苟琛岃繍琛屻€佹棤鐘舵€併€佸彧鍒嗘瀽涓嶅喅绛?- **宸插疄鐜?*锛歚market_analyst`銆乣news_analyst`銆乣sentiment_analyst`銆乣fundamentals_analyst`
- **鏁版嵁瀛樺偍**锛氬師濮嬫姤鍛婂瓨鍌ㄥ湪 `analyst_reports` 琛紝7 鏃ユ粴鍔ㄦ憳瑕佸瓨鍌ㄥ湪 `analyst_summaries` 琛?
#### Memory 绯荤粺
- **SQLite 鏁版嵁搴?* (`memory.db`)锛?  - `analyst_reports`锛氬垎鏋愬笀鍘熷鎶ュ憡
  - `analyst_summaries`锛? 鏃ユ粴鍔ㄧ粨鏋勫寲鎽樿锛堟妧鏈€佹柊闂汇€佹儏缁€佸熀鏈潰锛?  - `daily_trading_summaries`锛氭瘡鏃ヤ氦鏄撴憳瑕侊紙甯傚満鐘舵€併€佺瓥鐣ャ€佹敹鐩婄瓑锛?  - `cycle_reflections`锛氬懆鏈熷弽鎬濊褰曪紙閿欒妯″紡銆佹垚鍔熸ā寮忕瓑锛?- **ChromaDB**锛歚FinancialSituationMemory` 鍚戦噺璁板繂锛堥暱鏈熺粡楠岃蹇嗭級
- **History Maintainer**锛氳嚜鍔ㄧ淮鎶?7 鏃ユ粴鍔ㄦ憳瑕?
#### 鍐崇瓥妯″潡锛圥re-Open锛?- **Research Manager**锛氭暣鍚堝洓涓?Analyst 鎽樿 + Bull/Bear 杈╄锛岃緭鍑?`investment_plan`
- **Risk Manager**锛氬熀浜?Research Plan + 椋庨櫓杈╄锛岃緭鍑洪闄╃害鏉熷拰 `final_trade_decision`
- **Strategy Selector**锛氭牴鎹競鍦虹姸鎬侊紙`market_regime`锛夊拰椋庨櫓鍐崇瓥锛岄€夋嫨浜ゆ槗绛栫暐锛坄selected_strategy`锛夊拰棰勬湡琛屼负锛坄expected_behavior`锛?- **Trader**锛氭牴鎹瓥鐣ラ€夋嫨锛岀‘瀹氫氦鏄撴柟鍚戯紙BUY/SELL/HOLD锛夊拰姝㈢泩姝㈡崯瑙勫垯

#### 鎵ц妯″潡
- **Market Open**锛氭墽琛屼氦鏄撳喅绛栵紝姣忓ぉ鏈€澶氭墽琛屼竴娆′氦鏄?- **Post Close**锛氭洿鏂版寔浠撲环鏍硷紝璁＄畻鏃ユ敹鐩婄巼鍜屽洖鎾わ紝淇濆瓨 `daily_trading_summary`
- **History Maintainer**锛氭洿鏂?7 鏃ユ粴鍔ㄦ憳瑕侊紝渚涗笅涓€浜ゆ槗鏃ヤ娇鐢?
#### 鍛ㄦ湡绾фā鍧?- **Stock Selector**锛氬鍥犲瓙閫夎偂锛堝姩閲忋€佹尝鍔ㄧ巼銆丷SI銆佹垚浜ら噺銆佽秼鍔垮己搴︼級锛屾敮鎸?IC 鍔ㄦ€佹潈閲嶅拰甯傚満鐘舵€佹潈閲?- **Portfolio Manager**锛氱粍鍚堢鐞嗭紙鎸佷粨銆佺幇閲戙€佷氦鏄撴墽琛屻€佸啀骞宠　锛?- **Reflector Agent**锛氬懆鏈熺粨鏉熷弽鎬濓紝鎬荤粨閿欒妯″紡銆佹垚鍔熸ā寮忋€佺瓥鐣ラ€傜敤鏉′欢锛屾洿鏂伴暱鏈熻蹇?
---

## 涓夈€佸叧閿唬鐮佷綅缃?
### 3.1 涓昏杩愯鑴氭湰

| 鑴氭湰 | 璺緞 | 鍔熻兘 |
|------|------|------|
| 鍗曟爣鐨勫洖娴?| `run_single_symbol_backtest.py` | 鍗曟爣鐨勩€佸鏃ュ洖娴嬶紙瀹屾暣娴佺▼锛?|
| 澶氭爣鐨勫洖娴?| `run_multi_symbol_backtest.py` | 澶氭爣鐨勩€佸鍛ㄦ湡鍥炴祴锛堝寘鍚€夎偂鍜岃皟浠擄級 |
| 鍛ㄦ湡鍙嶆€?| `run_reflector_cycle.py` | 杩愯鍙嶆€濅唬鐞嗭紝鎬荤粨鍛ㄦ湡鍐呯殑浜ゆ槗缁忛獙 |

### 3.2 鏍稿績妯″潡

#### 鍥惧畾涔?- **涓讳氦鏄撳浘**锛歚tradingagents/graph/trading_graph.py`
- **Research 瀛愬浘**锛歚tradingagents/graph/research_subgraph.py`
- **Risk 瀛愬浘**锛歚tradingagents/graph/risk_subgraph.py`

#### Agent 鑺傜偣
- **Analyst 鑺傜偣**锛?  - `tradingagents/agents/market_analyst/agent.py`
  - `tradingagents/agents/news_analyst/agent.py`
  - `tradingagents/agents/sentiment_analyst/agent.py`
  - `tradingagents/agents/fundamentals_analyst/agent.py`
- **Pre-Open 鑺傜偣**锛?  - `tradingagents/agents/pre_open/researchers/bull_researcher.py`
  - `tradingagents/agents/pre_open/researchers/bear_researcher.py`
  - `tradingagents/agents/pre_open/managers/research_manager/agent.py`
  - `tradingagents/agents/pre_open/managers/risk_manager/agent.py`
  - `tradingagents/agents/pre_open/managers/strategy_selector/agent.py`
  - `tradingagents/agents/pre_open/trader/trader.py`
- **鎵ц鑺傜偣**锛?  - `tradingagents/agents/market_open/node.py`
  - `tradingagents/agents/post_close/node.py`
  - `tradingagents/agents/post_close/history_maintainer.py`
  - `tradingagents/agents/post_close/reflector.py`

#### 鏍稿績鍔熻兘
- **鏁版嵁閫傞厤鍣?*锛歚tradingagents/core/data_adapter.py`
- **缁勫悎绠＄悊**锛歚tradingagents/core/portfolio/portfolio_manager.py`
- **閫夎偂鍣?*锛歚tradingagents/core/selection/stock_selector.py`
- **绛栫暐搴?*锛歚tradingagents/core/strategies/strategy_lib.py`
- **鏁版嵁搴撴搷浣?*锛歚tradingagents/agents/utils/memory_db_helper.py`

#### Prompt 妯℃澘
- 鎵€鏈?Prompt 妯℃澘浣嶄簬鍚?Agent 鐩綍涓嬬殑 `prompt.j2` 鏂囦欢
- 渚嬪锛歚tradingagents/agents/pre_open/trader/prompt.j2`

### 3.3 鏁版嵁婧?
- **yfinance 鎻愪緵鑰?*锛歚datasources/data_sources/yfinance_provider.py`
- **Alpha Vantage 鎻愪緵鑰?*锛歚datasources/data_sources/alpha_vantage_provider.py`

### 3.4 鐘舵€佺鐞?
- **AgentState 瀹氫箟**锛歚tradingagents/agents/utils/agentstate/agent_states.py`
- **鐘舵€佸瓧娈佃鏄?*锛?  - `today_report`锛氬綋鏃ュ洓浣嶅垎鏋愬笀鎶ュ憡
  - `history_report`锛? 鏃ユ粴鍔ㄦ憳瑕?  - `past_memory_str`锛氶暱鏈熺粡楠岃蹇嗭紙鍚戦噺妫€绱級
  - `strategy_selection`锛氱瓥鐣ラ€夋嫨缁撴灉
  - `trader_plan`锛氫氦鏄撳憳璁″垝

---

## 鍥涖€佹暟鎹簱缁撴瀯

### 4.1 琛ㄧ粨鏋勬瑙?
#### `analyst_reports`
瀛樺偍鍒嗘瀽甯堝師濮嬫姤鍛娿€?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| id | INTEGER | 涓婚敭 |
| date | TEXT | 鏃ユ湡 |
| symbol | TEXT | 鑲＄エ浠ｇ爜 |
| analyst_type | TEXT | 鍒嗘瀽甯堢被鍨嬶紙market/news/sentiment/fundamentals锛?|
| report_content | TEXT | 鎶ュ憡鍐呭锛圝SON 瀛楃涓诧級 |
| created_at | TIMESTAMP | 鍒涘缓鏃堕棿 |

#### `analyst_summaries`
瀛樺偍 7 鏃ユ粴鍔ㄧ粨鏋勫寲鎽樿銆?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| id | INTEGER | 涓婚敭 |
| date | TEXT | 鏃ユ湡 |
| symbol | TEXT | 鑲＄エ浠ｇ爜 |
| market_summary | TEXT | 鎶€鏈垎鏋愭憳瑕侊紙JSON 瀛楃涓诧級 |
| news_summary | TEXT | 鏂伴椈鎽樿锛圝SON 瀛楃涓诧級 |
| sentiment_summary | TEXT | 鎯呯华鎽樿锛圝SON 瀛楃涓诧級 |
| fundamentals_summary | TEXT | 鍩烘湰闈㈡憳瑕侊紙JSON 瀛楃涓诧級 |
| created_at | TIMESTAMP | 鍒涘缓鏃堕棿 |

#### `daily_trading_summaries`
瀛樺偍姣忔棩浜ゆ槗鎽樿銆?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| id | INTEGER | 涓婚敭 |
| date | TEXT | 鏃ユ湡 |
| symbol | TEXT | 鑲＄エ浠ｇ爜 |
| market_regime | TEXT | 甯傚満鐘舵€?|
| selected_strategy | TEXT | 閫夋嫨鐨勭瓥鐣?|
| expected_behavior | TEXT | 棰勬湡琛屼负 |
| actual_return | REAL | 瀹為檯鏀剁泭鐜?|
| actual_max_drawdown | REAL | 瀹為檯鏈€澶у洖鎾?|
| positioning | TEXT | 浠撲綅鎯呭喌 |
| anomaly | TEXT | 寮傚父鎯呭喌 |
| summary_json | TEXT | 瀹屾暣鎽樿锛圝SON 瀛楃涓诧級 |
| created_at | TIMESTAMP | 鍒涘缓鏃堕棿 |

#### `cycle_reflections`
瀛樺偍鍛ㄦ湡鍙嶆€濊褰曘€?
| 瀛楁 | 绫诲瀷 | 璇存槑 |
|------|------|------|
| id | INTEGER | 涓婚敭 |
| cycle_type | TEXT | 鍛ㄦ湡绫诲瀷锛坵eekly/monthly锛?|
| cycle_start_date | TEXT | 鍛ㄦ湡寮€濮嬫棩鏈?|
| cycle_end_date | TEXT | 鍛ㄦ湡缁撴潫鏃ユ湡 |
| symbol | TEXT | 鑲＄エ浠ｇ爜锛堝彲閫夛級 |
| reflection_content | TEXT | 缁撴瀯鍖栧弽鎬濆唴瀹癸紙JSON 瀛楃涓诧級 |
| key_insights | TEXT | 鍏抽敭娲炲療 |
| error_patterns | TEXT | 閿欒妯″紡 |
| success_patterns | TEXT | 鎴愬姛妯″紡 |
| strategy_conditions | TEXT | 绛栫暐閫傜敤鏉′欢 |
| environment_biases | TEXT | 鐜鍒ゆ柇鍋忓樊 |
| created_at | TIMESTAMP | 鍒涘缓鏃堕棿 |

### 4.2 鏁版嵁搴撴搷浣?
浣跨敤 `MemoryDBHelper` 绫昏繘琛屾暟鎹簱鎿嶄綔锛?
```python
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper

db_helper = MemoryDBHelper("memory.db")

# 鏌ヨ鍒嗘瀽甯堟姤鍛?reports = db_helper.query_analyst_reports(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-01-31"
)

# 鏌ヨ姣忔棩浜ゆ槗鎽樿
summaries = db_helper.query_daily_trading_summaries_by_date_range(
    symbol="AAPL",
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

璇︾粏璇存槑璇峰弬鑰?`docs/鏁版嵁搴撲氦浜掓寚鍗?md`銆?
---

## 浜斻€佷娇鐢ㄦ寚鍗?
### 5.1 鐜鍑嗗

```bash
# 瀹夎鐜
conda create -n TradeSwarm python=3.12
conda activate TradeSwarm
pip install -r requirements.txt

# 鐜鍙橀噺锛?env 鎴?export锛?# LLM锛氫粎 Silicon Flow
export Silicon_API_KEY="your-silicon-key"
export base_url_silicon="https://api.siliconflow.cn/v1"   
# 鍙€夛細export SILICON_MODEL="Qwen/Qwen3-32B"
export ALPHA_VANTAGE_API_KEY="your-alpha-vantage-key"

# 鏁版嵁鎷夊彇闇€浠ｇ悊鏃讹紙yfinance 绛夋槗琚檺閫燂級
export USE_PROXY=true
export PROXY_HOST=127.0.0.1
export PROXY_PORT=7890
# 鎴栫洿鎺ヨ缃?HTTP_PROXY / HTTPS_PROXY
```

**娉ㄦ剰**锛歀LM 璋冪敤涓嶈兘璧颁唬鐞嗭紝浠ｇ爜涓細鍦ㄥ垱寤?LLM 鏃朵复鏃舵竻闄や唬鐞嗙幆澧冨彉閲忥紱鏁版嵁鎷夊彇鍓嶄細鏍规嵁 `USE_PROXY`/`PROXY_HOST` 鎭㈠浠ｇ悊銆?
### 5.2 閰嶇疆鏂囦欢

鍒涘缓 `config/config.yaml`锛?*LLM 鍑瘉浠ョ幆澧冨彉閲?`Silicon_API_KEY` 绛変负涓?*锛宍llm.silicon` 娈垫彁渚涢粯璁ゆā鍨嬩笌 base 鍥為€€锛?
```yaml
llm:
  silicon:
    api_key: ${Silicon_API_KEY}
    base_url: ${base_url_silicon}
    model_name: "Qwen/Qwen3-32B"
    temperature: 0.1

data_sources:
  tushare_token: ${TUSHARE_TOKEN}
  # 鈥﹀叾浣欒浠撳簱鍐?config/config.yaml 妯℃澘
```

### 5.3 杩愯绀轰緥

#### 鍗曟爣鐨勫洖娴?
```bash
# 瀹屾暣娴佺▼锛堟瘡鏃ヨ皟鐢?Analyst LLM + 鍐崇瓥 + 鎵ц锛?python run_single_symbol_backtest.py \
    --symbol NVDA \
    --start 2026-02-04 \
    --end 2026-02-12 \
    --cash 100000 \
    --db memory.db \
    --output backtest_results_nvda

# 浠呯敤 memory.db 涓凡鏈夋姤鍛婏紝涓嶈皟鐢?Analyst LLM锛堥€傚悎棰勬瀯寤烘暟鎹泦鍚庡揩閫熷洖娴嬶級
python run_single_symbol_backtest.py \
    --symbol NVDA --start 2026-02-04 --end 2026-02-12 \
    --db memory.db --output backtest_results_7days \
    --use-db-reports-only
```

#### 澶氭爣鐨勩€佸鍛ㄦ湡鍥炴祴

```bash
python run_multi_symbol_backtest.py \
    --start_date 2024-01-01 \
    --end_date 2024-01-31 \
    --cycle_type monthly \
    --initial_cash 1000000 \
    --db_path memory.db \
    --output_dir backtest_results_cycle
```

#### 鍛ㄦ湡鍙嶆€?
```bash
python run_reflector_cycle.py \
    --cycle_type weekly \
    --start_date 2024-01-01 \
    --end_date 2024-01-07 \
    --symbol AAPL \
    --db_path memory.db
```

### 5.4 宸ュ叿鑴氭湰

```bash
# 鏋勫缓 Analyst 鏁版嵁闆嗭紙鍐欏叆 memory.db锛屽彲閫夊鍑轰复鏃?JSON锛?# 鏁版嵁鎷夊彇璧颁唬鐞嗐€丩LM 涓嶈蛋浠ｇ悊锛汱LM 鍥哄畾 Silicon Flow锛?env 閰嶇疆瀵嗛挜锛?python scripts/experimental/build_analyst_dataset.py --symbol NVDA --trading-days 7 --end 2026-02-13 --db memory.db
# 浠呬粠 DB 瀵煎嚭 JSON锛堜笉璋冪敤 LLM锛?python scripts/experimental/build_analyst_dataset.py --symbol NVDA --trading-days 7 --end 2026-02-13 --db memory.db --export-only

# 鍥炴祴涓€斾腑鏂椂锛屼粠宸叉湁 daily_results 鑱氬悎鍑?backtest_report.json
python aggregate_backtest_report.py --output-dir backtest_results_7days

# 杩愯 Analyst 骞朵繚瀛樺埌鏁版嵁搴?python scripts/experimental/run_analysts_to_db.py

# 浠庢憳瑕佽繍琛屽畬鏁村浘
python scripts/experimental/run_graph_from_summary.py
```

璇︾粏璇存槑璇峰弬鑰?`docs/杩愯鎸囧崡.md`銆?
---

## 鍏€佹渶杩戝洖娴嬬粨鏋滅ず渚?
### 6.1 NVDA 鍥炴祴锛?025-11-06 鑷?2025-11-08锛?
**鍥炴祴鍙傛暟**锛?- 鏍囩殑锛歂VDA
- 鏃ユ湡鑼冨洿锛?025-11-06 鑷?2025-11-08
- 鍒濆璧勯噾锛?00,000
- 杈撳嚭鐩綍锛歚backtest_results_nvda`

**缁撴灉鎽樿**锛?- **浜ゆ槗鏃ユ暟**锛? 澶╋紙11-06銆?1-07锛?1-08 涓哄懆鍏紝闈炰氦鏄撴棩锛?- **鎬讳氦鏄撴暟**锛?
- **鏈€缁堝噣鍊?*锛?00,000锛堟棤浜ゆ槗锛?
**璇︾粏缁撴灉**锛?- **2025-11-06**锛?  - 鎵€鏈夊垎鏋愬笀鎶ュ憡鐢熸垚鎴愬姛
  - Pre-Open 瀹屾垚锛歍rader 寤鸿 BUY锛孲trategy Selector 閫夋嫨 `trend_following`锛孯isk Manager 鎵瑰噯 BUY锛堜粨浣?30%锛?  - Market Open 鏈墽琛屼氦鏄擄紙`market_open` 涓虹┖锛?  - 鏈€缁堟棤鎸佷粨

- **2025-11-07**锛?  - fundamentals 鍜?sentiment 鍒嗘瀽甯堥亣鍒拌繛鎺ラ敊璇?  - Pre-Open 鎵ц澶辫触锛堝洜涓鸿繛鎺ラ敊璇級
  - 娌℃湁浜ゆ槗

**闂鍒嗘瀽**锛?- 11-06 铏界劧 Risk Manager 鎵瑰噯浜?BUY锛屼絾 Market Open 娌℃湁鎵ц浜ゆ槗锛岄渶瑕佽皟璇?`market_open/node.py` 鐨勬墽琛岄€昏緫
- 11-07 鍥犱负 API 杩炴帴閿欒瀵艰嚧 Pre-Open 澶辫触锛岄渶瑕佸鐞?API 闄愬埗鍜岄敊璇噸璇?
**缁撴灉鏂囦欢浣嶇疆**锛?- 姣忔棩缁撴灉锛歚backtest_results_nvda/daily_results/YYYY-MM-DD.json`
- 鍥炴祴鎶ュ憡锛歚backtest_results_nvda/backtest_report.json`

### 6.2 NVDA 涓冩棩鍥炴祴锛?026-02-04 鑷?2026-02-12锛?
**娴佺▼**锛氬厛鐢?`scripts/experimental/build_analyst_dataset.py` 涓?NVDA 鏋勫缓 7 涓氦鏄撴棩鐨?Analyst 鎶ュ憡骞跺啓鍏?`memory.db`锛屽啀浣跨敤 `run_single_symbol_backtest.py --use-db-reports-only` 鍦ㄧ浉鍚岀獥鍙ｅ唴璺戝喅绛栦笌鎵ц锛屼笉閲嶅璋冪敤 Analyst LLM銆?
**鍥炴祴鍙傛暟**锛?- 鏍囩殑锛歂VDA
- 鏃ユ湡鑼冨洿锛?026-02-04 鑷?2026-02-12锛? 涓氦鏄撴棩锛?- 鍒濆璧勯噾锛?00,000
- 杈撳嚭鐩綍锛歚backtest_results_7days`
- LLM锛歋ilicon Flow锛圦wen/Qwen3-32B锛夌敤浜?Pre-Open 鍐崇瓥锛汚nalyst 鎶ュ憡鏉ヨ嚜 DB

**缁撴灉鎽樿**锛?- 浜ゆ槗鏃ユ暟锛?锛堜笌 daily_results 涓€鑷达級
- 鎬绘敹鐩?鎬讳氦鏄擄細瑙?`backtest_results_7days/backtest_report.json`
- 鑻ュ洖娴嬫湭璺戝畬鍗充腑鏂紝鍙敤 `aggregate_backtest_report.py --output-dir backtest_results_7days` 浠庡凡鏈?daily_results 鐢熸垚姹囨€绘姤鍛娿€?
---

## 涓冦€佸凡鐭ラ棶棰樹笌闄愬埗

### 7.1 API 璁块棶闄愬埗

**闂鎻忚堪**锛?- Alpha Vantage API 鏈夋棩璁块棶闄愬埗锛堝厤璐圭増閫氬父涓?5 娆?鍒嗛挓锛?00 娆?澶╋級
- 鍦ㄨ繍琛岄€夎偂鍜屽啀骞宠　鏃讹紝闇€瑕佷负澶氬彧鑲＄エ鑾峰彇鏁版嵁锛屽彲鑳借Е鍙?API 闄愬埗

**褰卞搷鑼冨洿**锛?- `run_multi_symbol_backtest.py` - 澶氭爣鐨勫洖娴嬪湪閫夎偂闃舵鍙兘閬囧埌闄愬埗
- Analyst 鑺傜偣鍦?API 闄愬埗涓嬪彲鑳藉け璐?
**瑙ｅ喅鏂规**锛?1. **浣跨敤缂撳瓨鏁版嵁**锛歚DataAdapter` 宸叉敮鎸佺紦瀛橈紝鏁版嵁涓嬭浇鍚庝細鑷姩淇濆瓨
2. **鍒嗘壒澶勭悊**锛氬湪閫夎偂鏃讹紝鍙互鍒嗘壒鑾峰彇鏁版嵁锛岄伩鍏嶄竴娆℃€ц姹傝繃澶?3. **浣跨敤鏈湴鏁版嵁**锛氬鏋滄湁鍘嗗彶鏁版嵁鏂囦欢锛屽彲浠ョ洿鎺ヤ娇鐢?4. **绛夊緟鏃堕棿**锛氬湪 API 闄愬埗涔嬮棿娣诲姞閫傚綋鐨勫欢杩?
**涓存椂澶勭悊**锛?- 鍦?API 闄愬埗鎯呭喌涓嬶紝鍙互锛?  - 浣跨敤杈冨皬鐨勮偂绁ㄦ睜杩涜娴嬭瘯锛堝 `STOCK_POOL[:20]`锛?  - 浣跨敤宸茬紦瀛樼殑鏁版嵁
  - 璺宠繃閫夎偂娴嬭瘯锛岀洿鎺ヤ娇鐢ㄥ浐瀹氭爣鐨勫垪琛?
璇︾粏璇存槑璇峰弬鑰?`KNOWN_ISSUES.md`銆?
### 7.2 Market Open 鎵ц闂

**闂鎻忚堪**锛?- 鍦ㄦ煇浜涙儏鍐典笅锛屽嵆浣?Risk Manager 鎵瑰噯浜嗕氦鏄擄紝Market Open 涔熷彲鑳戒笉鎵ц浜ゆ槗
- 浠?NVDA 鍥炴祴缁撴灉鐪嬶紝11-06 鐨?`market_open` 瀛楁涓虹┖

**鍙兘鍘熷洜**锛?1. 绛栫暐鎵ц澶辫触
2. 鏃犳硶鑾峰彇涓嬩竴涓氦鏄撴棩
3. 鏃犳硶鑾峰彇鎵ц浠锋牸
4. 绛栫暐娌℃湁浜х敓 BUY 淇″彿

**闇€瑕佽皟璇?*锛?- 妫€鏌?`tradingagents/agents/market_open/node.py` 鐨勬墽琛岄€昏緫
- 娣诲姞璇︾粏鐨勬棩蹇楄緭鍑猴紝鏌ョ湅鍏蜂綋鏄摢涓潯浠舵病鏈夋弧瓒?
### 7.3 鍏朵粬闂

- **LLM 杈撳嚭鏍煎紡**锛氶儴鍒?LLM 杈撳嚭鍙兘涓嶇鍚?JSON Schema锛岄渶瑕佸寮?JSON 鎻愬彇閫昏緫
- **閿欒澶勭悊**锛氶儴鍒嗚妭鐐瑰湪閬囧埌閿欒鏃跺彲鑳芥病鏈変紭闆呴檷绾э紝闇€瑕佸寮洪敊璇鐞?
---

## 鍏€佸緟鍔炰簨椤?
### 8.1 宸插畬鎴?鉁?
- 鉁?**鍗曟爣鐨勫鏃ュ洖娴嬮┍鍔ㄥ櫒**锛歚run_single_symbol_backtest.py`
- 鉁?**daily_trading_summaries 琛?*锛氭瘡鏃ヤ氦鏄撴憳瑕佽褰?- 鉁?**鏍囧噯鍖栧喅绛栧瓧娈?*锛歋trategy Selector 杈撳嚭 `market_regime`銆乣selected_strategy`銆乣expected_behavior`
- 鉁?**Market Open 鎵ц閫昏緫**锛氫氦鏄撴墽琛屻€佹瘡澶╂渶澶氫竴娆′氦鏄撶害鏉?- 鉁?**Post Close 鏀剁泭璁＄畻**锛氭棩鏀剁泭鐜囥€佸洖鎾よ绠?- 鉁?**鍛ㄦ湡绾?Reflector Agent**锛氶敊璇ā寮忋€佹垚鍔熸ā寮忔€荤粨
- 鉁?**鎴潰鍥犲瓙閫夎偂涓庡啀骞宠　**锛氬鍥犲瓙閫夎偂銆両C 鍔ㄦ€佹潈閲嶃€佸競鍦虹姸鎬佹潈閲?- 鉁?**澶氭爣鐨勩€佸鍛ㄦ湡鎸佺画杩愯鑴氭湰**锛歚run_multi_symbol_backtest.py`

### 8.2 寰呬紭鍖?
- [ ] **闆嗘垚 Analyst 鑺傜偣鍒颁富鍥?*锛氭浛浠?Summary 鑺傜偣鐩存帴鏌ヨ锛屽疄鐜板苟琛屾墽琛?- [ ] **瀛愬浘鎵ц浼樺寲**锛氳€冭檻骞惰鎵ц Research 鍜?Risk 瀛愬浘
- [ ] **绛栫暐搴撴墿灞?*锛氭坊鍔犳洿澶氫氦鏄撶瓥鐣?- [ ] **鍥犲瓙搴撴墿灞?*锛氶泦鎴?Alpha101 鍥犲瓙搴?- [ ] **瀹炴椂鐩戞帶**锛氱郴缁熺洃鎺ч潰鏉裤€佹€ц兘鎸囨爣鏀堕泦
- [ ] **鍙鍖?*锛氬洖娴嬬粨鏋滃彲瑙嗗寲銆佺瓥鐣ヨ〃鐜板垎鏋?- [ ] **Market Open 璋冭瘯**锛氫慨澶?Market Open 涓嶆墽琛屼氦鏄撶殑闂
- [ ] **API 閿欒澶勭悊**锛氬寮?API 闄愬埗鍜岄敊璇噸璇曟満鍒?
璇︾粏浠诲姟鍒楄〃璇峰弬鑰?`Project_TODOs.md`銆?
---

## 涔濄€佸紑鍙戣鑼?
### 9.1 浠ｇ爜瑙勮寖

- **绫诲瀷娉ㄨВ**锛氭墍鏈夊嚱鏁般€佹柟娉曞拰绫绘垚鍛橀兘蹇呴』鏈夌被鍨嬫敞瑙?- **鏂囨。瀛楃涓?*锛氫娇鐢?Google 椋庢牸鏂囨。瀛楃涓?- **浠ｇ爜鏍煎紡鍖?*锛氫娇鐢?Ruff 杩涜浠ｇ爜鏍煎紡鍖?- **娴嬭瘯瑕嗙洊**锛氫娇鐢?pytest 杩涜鍗曞厓娴嬭瘯

### 9.2 鏋舵瀯鍘熷垯

- **妯″潡鍖栬璁?*锛氭瘡涓ā鍧?鏂囦欢閮藉簲鍏锋湁瀹氫箟鏄庣‘鐨勫崟涓€鑱岃矗
- **鍙鐢ㄧ粍浠?*锛氬紑鍙戝彲澶嶇敤鐨勫嚱鏁板拰绫伙紝浼樺厛浣跨敤缁勫悎鑰岄潪缁ф壙
- **鐘舵€佺鐞?*锛氫娇鐢ㄧ粺涓€鐨?`AgentState` TypedDict 绠＄悊鐘舵€?- **閿欒澶勭悊**锛氫娇鐢ㄥ叿浣撶殑寮傚父绫诲瀷锛屾彁渚涗俊鎭赴瀵岀殑閿欒娑堟伅

### 9.3 Prompt 瑙勮寖

- **妯℃澘鍖?*锛氭墍鏈?Prompt 浣跨敤 Jinja2 妯℃澘锛坄.j2` 鏂囦欢锛?- **璇█**锛氫娇鐢ㄤ腑鏂囩紪鍐?Prompt
- **缁撴瀯鍖栬緭鍑?*锛氫娇鐢?JSON Schema 绾︽潫 LLM 杈撳嚭鏍煎紡
- **涓婁笅鏂囩鐞?*锛氬悎鐞嗕娇鐢ㄥ巻鍙叉憳瑕佸拰闀挎湡璁板繂

---

## 鍗併€侀噸瑕佹彁绀?
### 10.1 鐜鍙橀噺

- LLM锛氫粎 `Silicon_API_KEY` + 鍙€?`base_url_silicon` / `SILICON_MODEL`锛圫ilicon Flow锛夛紱`load_llm_from_config` 涓?Embedding/Chroma 瀹㈡埛绔悓鎹?`tradingagents/llm_env_compat.py`
- 鏁版嵁鎷夊彇锛氶渶瑕佷唬鐞嗘椂璁剧疆 `USE_PROXY=true` 鍙?`PROXY_HOST`/`PROXY_PORT`锛屾垨 `HTTP_PROXY`/`HTTPS_PROXY`
- Qwen/LLM 璋冪敤涓嶈兘璧颁唬鐞嗭紝绯荤粺浼氬湪鍒涘缓 LLM 鏃朵复鏃舵竻闄や唬鐞嗐€佹暟鎹媺鍙栧墠鎭㈠

### 10.2 鏁版嵁搴?
- 浣跨敤 SQLite 鏁版嵁搴擄紙`memory.db` 鐢ㄤ簬鐢熶骇锛夛紝浼氬湪棣栨杩愯鏃惰嚜鍔ㄥ垱寤?- 鏁版嵁搴撴枃浠跺彲鑳借緝澶э紝寤鸿瀹氭湡澶囦唤

### 10.3 API 闄愬埗

- Alpha Vantage 鏈夎皟鐢ㄩ鐜囬檺鍒讹紝绯荤粺宸插疄鐜板 API Key 杞鏈哄埗
- 寤鸿浣跨敤缂撳瓨鏁版嵁锛岄伩鍏嶉噸澶?API 璋冪敤

### 10.4 鍙傝€冧唬鐮?
- `trading_sys/` 鐩綍鍖呭惈鍙傝€冧唬鐮侊紙鍥犲瓙銆佺瓥鐣ャ€佺粍鍚堢鐞嗙瓑锛?- 瀹為檯浣跨敤鐨勪唬鐮佸凡闆嗘垚鍒?`tradingagents/` 涓紝涓嶅簲鐩存帴寮曠敤 `trading_sys/`

---

## 鍗佷竴銆佺浉鍏虫枃妗?
- [README.md](../README.md) - 椤圭洰涓绘枃妗?- [docs/鐩綍缁撴瀯璇存槑.md](鐩綍缁撴瀯璇存槑.md) - 璇︾粏鐨勭洰褰曠粨鏋勮鏄?- [docs/杩愯鎸囧崡.md](杩愯鎸囧崡.md) - 绯荤粺杩愯鎸囧崡
- [docs/鏁版嵁搴撲氦浜掓寚鍗?md](鏁版嵁搴撲氦浜掓寚鍗?md) - 鏁版嵁搴撴搷浣滄寚鍗?- [docs/褰撳墠鏁版嵁搴撹〃缁撴瀯.md](褰撳墠鏁版嵁搴撹〃缁撴瀯.md) - 鏁版嵁搴撹〃缁撴瀯璇存槑
- [Project_TODOs.md](../Project_TODOs.md) - 椤圭洰寰呭姙浜嬮」
- [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) - 宸茬煡闂璁板綍

---

## 鍗佷簩銆佽仈绯绘柟寮忎笌鏀寔

濡傛湁闂鎴栭渶瑕佽繘涓€姝ヨ鏄庯紝璇峰弬鑰冿細
1. 椤圭洰鏂囨。锛坄docs/` 鐩綍锛?2. 浠ｇ爜娉ㄩ噴鍜屾枃妗ｅ瓧绗︿覆
3. 宸茬煡闂璁板綍锛坄KNOWN_ISSUES.md`锛?
---

---

## 鍗佷笁銆佹湰娆′氦鎺ヨ鏄庯紙2026-02-20锛?
### 13.1 鏈樁娈靛畬鎴愬唴瀹?
- **鏁版嵁闆嗘瀯寤?*锛歚scripts/experimental/build_analyst_dataset.py` 鏀寔鎸夈€屾渶杩?N 涓氦鏄撴棩銆嶇敓鎴?Analyst 鎶ュ憡锛屽啓鍏?`memory.db`锛屽苟鍙鍑轰复鏃?JSON锛?*LLM 鍥哄畾 Silicon Flow**锛坄--export-only` 浠呬粠 DB 瀵煎嚭锛夈€?- **浠ｇ悊涓?LLM 鍒嗙**锛氭暟鎹媺鍙栵紙yfinance/浜ゆ槗鏃ュ巻锛夐渶浠ｇ悊鏃跺湪 .env 涓厤缃紱LLM 鍒濆鍖栧墠涓存椂娓呴櫎浠ｇ悊鐜鍙橀噺锛屽垵濮嬪寲鍚庢仮澶嶏紝閬垮厤 LLM 璧颁唬鐞嗐€?- **DataAdapter 鏃跺尯淇**锛歽finance 杩斿洖甯︽椂鍖?Index 涓?naive 鏃ユ湡姣旇緝浼氭姤閿欙紝宸插湪 `tradingagents/core/data_adapter.py` 涓粺涓€鏃跺尯澶勭悊锛堣 `KNOWN_ISSUES.md`锛夈€?- **memory.db 鍘婚噸**锛歚MemoryDBHelper.insert_report_or_update` 鎸?(analyst_type, symbol, trade_date) 鏇存柊鎴栨彃鍏ワ紝閬垮厤閲嶅鏉★紱鏋勫缓鏁版嵁闆嗘椂浣跨敤璇ユ柟娉曘€?- **鍥炴祴浠?DB 璇绘姤鍛?*锛歚run_single_symbol_backtest.py` 澧炲姞 `--use-db-reports-only`锛屽綋鏃?Analyst 鎶ュ憡鐩存帴浠?`memory.db` 璇诲彇锛屼笉璋冪敤 Analyst LLM锛岄€傚悎棰勬瀯寤烘暟鎹泦鍚庣殑蹇€熷洖娴嬨€?- **鍥炴祴寮傚父涓庤仛鍚堟姤鍛?*锛氫富寰幆鍖呭湪 try/except 涓紝寮傚父鏃朵粛浼氬啓鍏ュ凡瀹屾垚鐨?daily_results 骞剁敓鎴?`backtest_report.json`锛涜嫢涓€斾腑鏂湭鐢熸垚鎶ュ憡锛屽彲鐢?`aggregate_backtest_report.py --output-dir <dir>` 浠庡凡鏈?daily_results 鑱氬悎銆?- **閰嶇疆涓庢枃妗?*锛歚config/config.yaml` 鐨?`llm.silicon` 涓?`.env` 鐨?`Silicon_API_KEY` 绛変负鍗曚竴 LLM 鏉ユ簮锛沗README.md` / `docs/DATA_LAB.md` 宸插悓姝ャ€屼粎 Silicon銆佹棤 `--use-silicon`銆嶏紱`KNOWN_ISSUES.md` 璁板綍 yfinance 鏃跺尯闂涓庝慨澶嶃€?
### 13.2 宸茬Щ闄ょ殑涓存椂鏂囦欢锛堟湰娆℃暣鐞嗭級

- `test_spy_fetch.py`锛氬崟鐙祴璇?SPY 鏁版嵁鎷夊彇涓庝唬鐞嗙殑鑴氭湰锛堣瘖鏂敤锛屽凡鍒狅級銆?- `analyst_dataset_*_temp.json`锛氭瀯寤烘暟鎹泦鏃跺鍑虹殑涓存椂 JSON锛堝凡鍒狅紱鏂板鍑轰細鍖归厤 `.gitignore` 涓殑 `analyst_dataset_*_temp.json`锛夈€?
### 13.3 鎺ㄨ崘瀹為獙娴佺▼锛堜竷鏃ョ獥鍙ｇず渚嬶級

1. **鏋勫缓 7 鏃?Analyst 鏁版嵁**锛堥渶浠ｇ悊 + Silicon LLM 鍙敤锛? 
   `python scripts/experimental/build_analyst_dataset.py --symbol NVDA --trading-days 7 --end 2026-02-13 --db memory.db`
2. **鍥炴祴锛堜粎鐢?DB 鎶ュ憡锛屼笉閲嶈窇 Analyst锛?*  
   `python run_single_symbol_backtest.py --symbol NVDA --start 2026-02-04 --end 2026-02-12 --db memory.db --output backtest_results_7days --use-db-reports-only`
3. **鏌ョ湅鏀剁泭**  
   鏌ョ湅 `backtest_results_7days/backtest_report.json`锛涜嫢鏈敓鎴愬垯杩愯  
   `python aggregate_backtest_report.py --output-dir backtest_results_7days`

### 13.4 浠ｇ爜涓庢枃妗ｄ綅缃€熸煡

| 鐢ㄩ€?          | 浣嶇疆 |
|----------------|------|
| 鏋勫缓 Analyst 鏁版嵁闆?| `scripts/experimental/build_analyst_dataset.py` |
| 鍗曟爣鐨勫洖娴嬶紙鍚?--use-db-reports-only锛?| `run_single_symbol_backtest.py` |
| 浠?partial 缁撴灉鑱氬悎鎶ュ憡 | `aggregate_backtest_report.py` |
| LLM 鍔犺浇锛堝惈 Silicon/浠ｇ悊澶勭悊锛?| `tradingagents/graph/utils.py` 鈫?`load_llm_from_config` |
| 鎶ュ憡鍐欏叆/鍘婚噸 | `tradingagents/agents/utils/memory_db_helper.py` 鈫?`insert_report_or_update` |
| 鏃跺尯涓庢暟鎹媺鍙?| `tradingagents/core/data_adapter.py`锛涚粡楠岃褰曡 `KNOWN_ISSUES.md` |

---

**鏈€鍚庢洿鏂?*: 2026-02-20  
**缁存姢鑰?*: TradeSwarm Team

