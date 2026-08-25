"""
Юнит-тесты для generate_config — раскладки настроек бота по ключам freqtrade.

Это единственное место, где депозит пользователя превращается в размер сделки, и
ошибиться здесь дороже всего: freqtrade молча торгует тем, что написано в конфиге.
Реальные боты уже отработали с перепутанной раскладкой — депозит уезжал в
stake_amount (размер ОДНОЙ сделки), dry_run_wallet оставался шаблонной тысячей, и
бот с депозитом 100 USDT торговал по 100 USDT со счёта в 1000. Тесты ниже держат
именно это соответствие.

Без сети и без БД: generate_config только читает шаблон с диска и возвращает dict.
"""

import pytest

from src.services.freqtrade_config import generate_config

# ──────────────────────────────────────────────
# Хелпер: вызов с осмысленными дефолтами, тест задаёт только то,
# что проверяет (депозит, долю, режим).
# ──────────────────────────────────────────────


async def make_config(*, deposit: float, stake_ratio: float, dry_run: bool = True) -> dict:
    return await generate_config(
        pair="AVAX/USDT:USDT",
        api_port_inside_container=8080,
        jwt_secret="jwt",
        ws_token="ws",
        api_username="freqtrader",
        api_password="pwd",
        exchange_key="",
        exchange_secret="",
        deposit=deposit,
        stake_ratio=stake_ratio,
        user_id=1,
        dry_run=dry_run,
    )


# ──────────────────────────────────────────────
# Депозит и размер сделки
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stake_amount_is_deposit_times_ratio():
    # Arrange / Act
    cfg = await make_config(deposit=100.0, stake_ratio=0.2)

    # Assert: 20% от депозита 100 — это 20 USDT на сделку, а не 100
    assert cfg["stake_amount"] == 20.0


@pytest.mark.asyncio
async def test_dry_run_wallet_equals_deposit():
    # Arrange / Act
    cfg = await make_config(deposit=100.0, stake_ratio=0.2)

    # Assert: кошелёк симуляции — депозит пользователя, а не дефолтная 1000 из шаблона.
    # Иначе бот с депозитом 100 может «потерять» несколько сотен, чего на реальном
    # счёте физически не бывает — он был бы ликвидирован раньше.
    assert cfg["dry_run_wallet"] == 100.0


@pytest.mark.asyncio
async def test_available_capital_equals_deposit():
    # Arrange / Act
    cfg = await make_config(deposit=100.0, stake_ratio=0.2, dry_run=False)

    # Assert: в live-режиме dry_run_wallet не используется, и без available_capital
    # бот считал бы своим весь баланс биржи, а не выделенный ему депозит
    assert cfg["available_capital"] == 100.0


@pytest.mark.asyncio
async def test_tradable_balance_ratio_is_not_set():
    # Arrange / Act
    cfg = await make_config(deposit=100.0, stake_ratio=0.2)

    # Assert: available_capital перекрывает tradable_balance_ratio (freqtrade берёт
    # первый и игнорирует второй). Оставить оба — значит положить в конфиг две
    # противоречащие друг другу величины и гадать, какая сработала.
    assert "tradable_balance_ratio" not in cfg


@pytest.mark.asyncio
async def test_full_ratio_spends_whole_deposit_in_one_trade():
    # Arrange / Act
    # Граница: 100% от депозита. Сделка равна всему капиталу — freqtrade это допускает
    # (отказ идёт строго при stake_amount > available_capital), проверяем, что мы не
    # выходим за неё округлением.
    cfg = await make_config(deposit=555.0, stake_ratio=1.0)

    # Assert
    assert cfg["stake_amount"] == 555.0
    assert cfg["stake_amount"] <= cfg["available_capital"]


@pytest.mark.asyncio
async def test_stake_amount_never_exceeds_available_capital():
    # Arrange / Act
    # Пятый тестовый бот на сервере простоял 4 дня без единой сделки именно из-за
    # обратного соотношения: stake_amount=1000 при доступных 500. freqtrade в этом
    # случае бросает DependencyException на каждом цикле и не открывает позицию.
    for ratio in (0.05, 0.2, 0.5, 0.95, 1.0):
        cfg = await make_config(deposit=1000.0, stake_ratio=ratio)

        # Assert
        assert cfg["stake_amount"] <= cfg["available_capital"], ratio


@pytest.mark.asyncio
async def test_fractional_stake_is_rounded_to_eight_digits():
    # Arrange / Act
    # 33.3 * 0.15 в double даёт 4.994999999999999 — в конфиг должно уехать число,
    # а не хвост из плавающей точки
    cfg = await make_config(deposit=33.3, stake_ratio=0.15)

    # Assert
    assert cfg["stake_amount"] == 4.995


# ──────────────────────────────────────────────
# Остальные поля, которые генератор обязан проставить
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pair_and_dry_run_flag_reach_config():
    # Arrange / Act
    cfg = await make_config(deposit=100.0, stake_ratio=0.2, dry_run=False)

    # Assert
    assert cfg["exchange"]["pair_whitelist"] == ["AVAX/USDT:USDT"]
    assert cfg["dry_run"] is False
