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


######
######
######
#  AMETHYST  DATA  #
######
######
######

class AmethystData:
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


######
######
######
#  AMETHYST  #
######
######
######
def amethyst(state: TradingState) -> List[Order]:
    orders = []
    order_depth: OrderDepth = state.order_depths["AMETHYSTS"]
    buy_price = 9_998
    sell_price = 10_002
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


######
######
######
#  STARFRUIT  DATA  #
######
######
######

class StarfruitData:
    PRICE_AMT = 10

    def __init__(self) -> None:
        self.last_bid_prices: List[float] = []
        self.last_ask_prices: List[float] = []
        self.long_at: dict[int, int] = {}
        self.short_at: dict[int, int] = {}

    def to_str(self) -> str:
        return jsonpickle.encode(self)

    def update_last_prices(self, ask: float, bid: float) -> None:
        next_bid_prices = []
        next_ask_prices = []
        if len(self.last_prices) > self.PRICE_AMT:
            next_bid_prices = self.last_prices[1:] + [bid]
            next_ask_prices = self.last_prices[1:] + [ask]
        else:
            next_bid_prices = self.last_prices + [bid]
            next_ask_prices = self.last_prices + [ask]

        self.last_bid_prices = next_bid_prices
        self.last_ask_prices = next_ask_prices


######
######
######
#  STARFRUIT  #
######
######
######

def starfruit(state: TradingState) -> tuple[List[Order], str]:
    orders = []
    position_limit = 20
    position = state.position.get("STARFRUIT", 0)
    order_depth: OrderDepth = state.order_depths["STARFRUIT"]

    data = StarfruitData()
    if state.traderData != "":
        data = jsonpickle.decode(state.traderData)

    min_profit = 4
    # max_loss = 3

    best_ask, _ = list(order_depth.sell_orders.items())[0]
    best_bid, _ = list(order_depth.buy_orders.items())[0]

    # Check if we can sell any owned STARFRUIT making at leas min_profit
    if len(data.long_at) > 0:
        asks = list(order_depth.sell_orders.items())
        asks.sort(key=lambda x: x[0], reverse=True)
        long_at = list(data.long_at.items())
        long_at.sort(key=lambda x: x[0])

        while len(asks) > 0 and len(long_at) > 0 and asks[0][0] >= data.long_at[0] + min_profit:
            amt_sold = max_sell_amt(position, position_limit, asks[0][1])

            logger.print("Selling", amt_sold, "STARFRUIT at", asks[0][0])
            orders.append(Order("STARFRUIT", asks[0][0], -amt_sold))
            position -= amt_sold

            if amt_sold == asks[0][1]:
                data.long_at[asks[0][0]] -= asks[0][1]
                asks.pop(0)
            if amt_sold == long_at[0][1]:
                data.long_at.pop(long_at[0][0])
                long_at.pop(0)
            if position == -position_limit:
                break

    # Check if we can buy any shorted STARFRUIT making at least min_profit
    if len(data.short_at) > 0:
        bids = list(order_depth.buy_orders.items())
        bids.sort(key=lambda x: x[0])
        short_at = list(data.long_at.items())
        short_at.sort(key=lambda x: x[0], reverse=True)

        while len(bids) > 0 and len(short_at) > 0 and bids[0][0] <= data.short_at[0] - min_profit:
            amt_buy = max_buy_amt(position, position_limit, bids[0][1])

            logger.print("Buying", amt_buy, "STARFRUIT at", bids[0][0])
            orders.append(Order("STARFRUIT", bids[0][0], amt_buy))
            position += amt_buy

            if amt_buy == bids[0][1]:
                data.short_at[bids[0][0]] -= bids[0][1]
                bids.pop(0)
            if amt_buy == short_at[0][1]:
                data.short_at.pop(short_at[0][0])
                short_at.pop(0)
            if position == position_limit:
                break

    avg_ask = sum(data.last_ask_prices) / len(data.last_ask_prices)
    if avg_ask > best_ask:
        amt_sell = max_sell_amt(position, position_limit, best_ask)

        logger.print("Selling", amt_sell, "STARFRUIT at", best_ask)
        orders.append(Order("STARFRUIT", best_ask, -amt_sell))
        position -= amt_sell
        data.short_at[best_ask] = amt_sell

    avg_bid = sum(data.last_bid_prices) / len(data.last_bid_prices)
    if avg_bid < best_bid:
        amt_buy = max_buy_amt(position, position_limit, best_bid)

        logger.print("Buying", amt_buy, "STARFRUIT at", best_bid)
        orders.append(Order("STARFRUIT", best_bid, amt_buy))
        position += amt_buy
        data.long_at[best_bid] = amt_buy

    data.update_last_prices(best_ask, best_bid)

    return orders, jsonpickle.encode(data)
