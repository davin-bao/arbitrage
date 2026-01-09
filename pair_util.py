from itertools import combinations

import context


def sync_arb_pairs():
    """
    自动生成同币跨所 arb_pair（含风控过滤）
    """
    # 1️⃣ 取所有永续市场
    markets = context.db.fetch_all("perp_market")

    # 2️⃣ exchange 配置映射
    exchange_cfg = {
        row["id"]: row
        for row in context.db.fetch_all("exchange")
    }
    print(context.config)
    # 3️⃣ 按 base 分组
    markets_by_base = {}
    for m in markets:
        if m["quote"] != context.config.get('pair.quote'):
            print(f"跳过市场 {m['symbol']}，因为报价货币 {m['quote']} 不匹配配置中的 {context.config.get('pair.quote')}")
            continue

        markets_by_base.setdefault(m["base"], []).append(m)

    created = 0

    # 4️⃣ 同一 base 两两组合
    for base, group in markets_by_base.items():
        if len(group) < 2:
            continue

        for m1, m2 in combinations(group, 2):

            # ❌ 同交易所
            if m1["exchange_id"] == m2["exchange_id"]:
               print(f"跳过 {m1['symbol']} 和 {m2['symbol']}，因为它们在同一个交易所")
               continue

            ex1 = exchange_cfg[m1["exchange_id"]]
            ex2 = exchange_cfg[m2["exchange_id"]]

            # ❌ 非 CEX
            if ex1["type"] != "cex" or ex2["type"] != "cex":
                print(f"跳过 {m1['symbol']} 和 {m2['symbol']}，因为其中至少一个不是CEX交易所")
                continue

            # ❌ 杠杆过低
            if (
                (m1["leverage_max"] or 100) < context.config.get('pair.minLeverage') or
                (m2["leverage_max"] or 100) < context.config.get('pair.minLeverage')
            ):
                print(f"跳过 {m1['symbol']} 和 {m2['symbol']}，因为杠杆过低（{m1['leverage_max']} 或 {m2['leverage_max']} 小于 {context.config.get('pair.minLeverage')}）")
                continue

            # ❌ 合约太小（流动性差）
            if (
                (m1["contract_size"] or 0) < context.config.get('pair.minContractSize') or
                (m2["contract_size"] or 0) < context.config.get('pair.minContractSize')
            ):
                print(f"跳过 {m1['symbol']} 和 {m2['symbol']}，因为合约面值太小（{m1['contract_size']} 或 {m2['contract_size']} 小于 {context.config.get('pair.minContractSize')}）")
                continue

            # 5️⃣ 固定 long / short 顺序（按 exchange_id 排序）
            long_market = m1 if m1["exchange_id"] < m2["exchange_id"] else m2
            short_market = m2 if long_market is m1 else m1

            # ❌ 已存在
            exists = context.db.fetch_one(
                "arb_pair",
                "market_long_id = ? AND market_short_id = ?",
                (long_market["id"], short_market["id"])
            )

            if exists:
                print(f"跳过 {long_market['symbol']} 和 {short_market['symbol']}，因为套利对已存在")
                continue

            # 6️⃣ 插入 arb_pair
            context.db.insert("arb_pair", {
                "market_long_id": long_market["id"],
                "market_short_id": short_market["id"],
                "strategy_type": "spread",  # 默认价差套利
                "active": 1
            })

            created += 1

    print(f"[OK] arb_pair created: {created}")
