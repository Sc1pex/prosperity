import json
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState
from typing import Any, List
import jsonpickle


class Logger:
    def __init__(self) -> None:
        self.logs = ""

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        print(json.dumps([
            self.compress_state(state),
            self.compress_orders(orders),
            conversions,
            trader_data,
            self.logs,
        ], cls=ProsperityEncoder, separators=(",", ":")))

        self.logs = ""

    def compress_state(self, state: TradingState) -> list[Any]:
        return [
            state.timestamp,
            state.traderData,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append(
                [listing["symbol"], listing["product"], listing["denomination"]])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [
                order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append([
                    trade.symbol,
                    trade.price,
                    trade.quantity,
                    trade.buyer,
                    trade.seller,
                    trade.timestamp,
                ])

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sunlight,
                observation.humidity,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed


logger = Logger()


class Trader:
    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        result = {}
        for product in state.order_depths:

            if (product == "AMETHYSTS"):
                result[product] = amethyst(state)
            elif (product == "STARFRUIT"):
                result[product], traderData = starfruit(state)

        conversions = 0
        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData


def max_buy_amt(position: int, position_limit: int, wanted_amt: int) -> int:
    return min(position_limit - position, wanted_amt)


def max_sell_amt(position: int, position_limit: int, wanted_amt: int) -> int:
    return min(position + position_limit, wanted_amt)


def amethyst(state: TradingState) -> List[Order]:
    orders = []
    order_depth: OrderDepth = state.order_depths["AMETHYSTS"]
    buy_price = 9_999
    sell_price = 10_001
    position_limit = 20

    if len(order_depth.sell_orders) != 0:
        best_ask, best_ask_amount = list(
            order_depth.sell_orders.items())[0]
        best_ask_amount = -best_ask_amount
        if best_ask <= buy_price:
            position = state.position.get("AMETHYSTS", 0)
            amt = max_buy_amt(
                position, position_limit, best_ask_amount)

            logger.print("Buying", amt, "AMETHYSTS at", best_ask)
            orders.append(Order("AMETHYSTS", best_ask, amt))

    if len(order_depth.buy_orders) != 0:
        best_bid, best_bid_amount = list(
            order_depth.buy_orders.items())[0]
        if best_bid >= sell_price:
            position = state.position.get("AMETHYSTS", 0)
            amt = max_sell_amt(
                position, position_limit, best_bid_amount)

            logger.print("Selling", amt, "AMETHYSTS at", best_bid)
            orders.append(Order("AMETHYSTS", best_bid, -amt))

    return orders


class StarfruitData:
    def __init__(self) -> None:
        self.last_prices: List[float] = []
        self.long_at: dict[int, int] = {}
        self.short_at: dict[int, int] = {}

    def to_str(self) -> str:
        return jsonpickle.encode(self)

    def update_last_prices(self, price: float) -> None:
        next_prices = []
        if len(self.last_prices) > 20:
            next_prices = self.last_prices[1:] + [price]
        else:
            next_prices = self.last_prices + [price]

        self.last_prices = next_prices


def starfruit(state: TradingState) -> tuple[List[Order], str]:
    orders = []
    position_limit = 20
    order_depth: OrderDepth = state.order_depths["STARFRUIT"]

    data = StarfruitData()
    if state.traderData != "":
        data = jsonpickle.decode(state.traderData)

    min_profit = 4
    max_loss = 3

    if len(data.long_at) > 0:
        best_bid = max(order_depth.buy_orders)
        best_bid_amt = order_depth.buy_orders[best_bid]
        for p, amt in data.long_at.items():
            price = int(p)
            # Sell at a profit
            if best_bid - price >= min_profit:
                sell_amt = min(amt, best_bid_amt)
                logger.print("Selling (gain)", sell_amt,
                             "STARFRUIT at", best_bid)
                orders.append(Order("STARFRUIT", best_bid, -sell_amt))

                if sell_amt == amt:
                    del data.long_at[price]
                else:
                    data.long_at[price] -= sell_amt
                break

            # Sell at max loss
            if price - best_bid >= max_loss:
                sell_amt = min(amt, best_bid_amt)
                logger.print("Selling (loss)", sell_amt,
                             "STARFRUIT at", best_bid)
                orders.append(Order("STARFRUIT", best_bid, -sell_amt))

                if sell_amt == amt:
                    del data.long_at[price]
                else:
                    data.long_at[price] -= sell_amt
                break

    if len(data.short_at) > 0:
        best_ask = min(order_depth.sell_orders)
        best_ask_amt = -order_depth.sell_orders[best_ask]
        for price, amt in data.short_at.items():
            # Buy at a profit
            if price - best_ask >= min_profit:
                sell_amt = min(amt, best_ask_amt)
                logger.print("Buying", sell_amt, "STARFRUIT at", best_ask)
                orders.append(Order("STARFRUIT", best_ask, sell_amt))

                if sell_amt == amt:
                    del data.short_at[price]
                else:
                    data.short_at[price] -= sell_amt
                break

            # Buy at max loss
            if best_ask - price >= max_loss:
                sell_amt = min(amt, best_ask_amt)
                logger.print("Buying", sell_amt, "STARFRUIT at", best_ask)
                orders.append(Order("STARFRUIT", best_ask, sell_amt))

                if sell_amt == amt:
                    del data.short_at[price]
                else:
                    data.short_at[price] -= sell_amt
                break

    diffs = []
    for i in range(1, len(data.last_prices)):
        diffs.append(data.last_prices[i] - data.last_prices[i-1])
    up, down = 0, 0
    for diff in diffs:
        if diff > 0:
            up += 1
        else:
            down += 1
    logger.print("Prices", data.last_prices)
    logger.print("Diffs", diffs)

    if up > down:
        logger.print("Market is going up. Buy")
        best_ask = min(order_depth.sell_orders)
        best_ask_amount = -order_depth.sell_orders[best_ask]
        position = state.position.get("STARFRUIT", 0)
        amt = max_buy_amt(
            position, position_limit, best_ask_amount)
        if amt > 0:
            logger.print("Buying", amt, "STARFRUIT at", best_ask)
            orders.append(Order("STARFRUIT", best_ask, amt))

            current_amt = data.long_at.get(best_ask, 0)
            data.long_at[best_ask] = current_amt + amt

    elif down < up:
        logger.print("Market is going down. Sell")
        best_ask = max(order_depth.buy_orders)
        best_ask_amount = order_depth.buy_orders[best_ask]
        position = state.position.get("STARFRUIT", 0)
        amt = max_sell_amt(
            position, position_limit, best_ask_amount)
        if amt > 0:
            logger.print("Selling", amt, "STARFRUIT at", best_ask)
            orders.append(Order("STARFRUIT", best_ask, -amt))

            current_amt = data.short_at.get(best_ask, 0)
            data.short_at[best_ask] = current_amt + amt

    midprice = (max(order_depth.buy_orders) + min(order_depth.sell_orders)) / 2
    data.update_last_prices(midprice)
    logger.print("Prices", data.last_prices, "  Midprice", midprice)

    return orders, jsonpickle.encode(data)
