# Рецепты: freqtrade в Bot_Service

Типовые задачи по шагам. Что означают сами настройки — в [README.md](README.md).

Команды бэкенда — из папки `backend/`, команды с `docker` — на сервере.

---

## Оглавление

- [Посмотреть, с какими настройками реально работает бот](#посмотреть-с-какими-настройками-реально-работает-бот)
- [Проверить здоровье бота руками](#проверить-здоровье-бота-руками)
- [Изменить настройку в конфиге для всех новых ботов](#изменить-настройку-в-конфиге-для-всех-новых-ботов)
- [Применить починку к уже работающему боту](#применить-починку-к-уже-работающему-боту)
- [Добавить новый индикатор](#добавить-новый-индикатор)
- [Добавить новое поле настройки](#добавить-новое-поле-настройки)
- [Проверить, что сгенерируется, не создавая бота](#проверить-что-сгенерируется-не-создавая-бота)
- [Посчитать, что настройки значат в деньгах](#посчитать-что-настройки-значат-в-деньгах)
- [Понять, по какой трактовке TP/SL работает старый бот](#понять-по-какой-трактовке-tpsl-работает-старый-бот)
- [Отладка: симптом → причина](#отладка-симптом--причина)
- [Чек-лист перед правкой шаблонов](#чек-лист-перед-правкой-шаблонов)

---

## Посмотреть, с какими настройками реально работает бот

Не с теми, что в базе, а с теми, что лежат в его папке — это разные вещи, если
шаблон менялся после создания бота.

```bash
# конфиг на диске
cat bots_data/<bot_id>/config.json | python -m json.tool

# блок настроек в стратегии
sed -n '/class StrategyConfig/,/^# ===/p' \
    bots_data/<bot_id>/user_data/strategies/MultiFilterStrategy.py

# что об этом думает сам freqtrade (нужны логин/пароль из таблицы bots)
curl -s -u <api_username>:<api_password> \
     http://127.0.0.1:<api_port>/api/v1/show_config | python -m json.tool
```

Последняя команда — самая надёжная: показывает, что бот действительно применил.

---

## Проверить здоровье бота руками

Ровно то же, что делает `polling_worker` каждые 30 секунд — полезно, когда бот в
статусе `error` и надо понять, на каком шаге он отвалился. Логин и пароль берутся из
таблицы `bots` (`api_username`, `api_password`), порт — оттуда же.

```bash
PORT=9000; USER=freqtrader; PASS=<api_password>

# 1. жив ли процесс freqtrade. Эта ручка БЕЗ авторизации
curl -s http://127.0.0.1:$PORT/api/v1/ping
# {"status":"pong"}

# 2. торгует ли он: running / paused / stopped
curl -s -u $USER:$PASS http://127.0.0.1:$PORT/api/v1/show_config \
  | python -c "import json,sys; print(json.load(sys.stdin)['state'])"

# 3. что он думает про сделки
curl -s -u $USER:$PASS "http://127.0.0.1:$PORT/api/v1/trades?limit=5" | python -m json.tool
curl -s -u $USER:$PASS http://127.0.0.1:$PORT/api/v1/status | python -m json.tool
```

Как читать результат:

| Что вышло | Что это значит |
|---|---|
| `ping` не отвечает | Процесс мёртв или ещё грузится. Воркер признаёт отказ после трёх промахов подряд (90 с) |
| `ping` есть, `state: stopped` | Freqtrade поймал `OperationalException` и встал. Контейнер при этом полностью здоров — причина только в `docker logs` |
| `ping` есть, `state: running`, сделок нет | Живой бот, который не находит входа. Смотреть фильтры и `stake_amount` |
| 401 на `show_config` | Пароль в БД разошёлся с `config.json` бота — бот создан с другим паролем |

Логи можно взять и через наш бэкенд — `GET /bots/{id}/logs` (он же
`docker logs` под капотом, до 200 строк). Но если freqtrade упал **до** подъёма своего
REST API, полезнее сразу смотреть `docker logs`: там будет причина падения.

---

## Изменить настройку в конфиге для всех новых ботов

Две ситуации, не путать их.

**Настройка одинаковая для всех ботов** — правим
[config.template.json](../../backend/src/templates/config.template.json), и всё.

**Настройка зависит от бота** — правим
[freqtrade_config.py](../../backend/src/services/freqtrade_config.py):

1. Добавить параметр в сигнатуру `generate_config()`.
2. Проставить ключ в `config[...]` в теле функции.
3. Передать значение из [bot_file_manager.py](../../backend/src/services/bot_file_manager.py).
4. Положить в шаблон placeholder с осмысленным дефолтом — чтобы файл оставался
   валидным конфигом сам по себе.
5. Написать тест в `tests/unit/test_freqtrade_config.py`.

Тест обязателен и обязан быть показан красным: сломайте строку, которую он
покрывает, убедитесь что упал, верните. В этом файле уже проверено 5 мутаций.

---

## Применить починку к уже работающему боту

Файлы бота генерируются **один раз при создании**. Ни перезапуск контейнера, ни
`git pull` на сервере на них не влияют.

**Вариант 1 — пересоздать бота** (правильный). Удалить через интерфейс и создать
заново с теми же настройками. Сделки не потеряются: удаление мягкое, строка в
`bots` остаётся с `is_active=0`, а `trades` не трогается вообще.

**Вариант 2 — переписать конфиг руками** (быстрый, для одного-двух ботов):

```bash
# 1. посмотреть настройки бота в нашей базе
sqlite3 backend/cryptobot.db \
  "SELECT id, name, stake_amount, tradable_balance_ratio, container_name
   FROM bots WHERE is_active = 1;"

# 2. поправить нужные ключи
python - <<'EOF'
import json
p = "bots_data/<bot_id>/config.json"
c = json.load(open(p, encoding="utf-8"))
deposit, ratio = 100.0, 0.2          # из запроса выше
c["dry_run_wallet"]    = deposit
c["available_capital"] = deposit
c["stake_amount"]      = round(deposit * ratio, 8)
c.pop("tradable_balance_ratio", None)
json.dump(c, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
EOF

# 3. перезапустить контейнер
docker restart <container_name>

# 4. убедиться, что бот применил новое
curl -s -u <user>:<pass> http://127.0.0.1:<port>/api/v1/show_config \
  | python -c "import json,sys; c=json.load(sys.stdin); print(c['stake_amount'], c.get('available_capital'))"
```

Открытые в этот момент сделки переживут перезапуск — они лежат в собственной базе
бота `user_data/tradesv3.sqlite` внутри примонтированной папки.

---

## Добавить новый индикатор

Сейчас поддерживаются `rsi`, `cci`, `mfi`, `bb_percent` (Bollinger %B) и `adx`.
Продуктовое правило проекта — простота, так что сначала стоит спросить, точно ли
индикатор нужен. Если да, трогать придётся четыре места — и все четыре обязательны:
индикатор, который прошёл схему, но не посчитан в шаблоне, **не даёт никакой ошибки**.
`_apply_filters` пишет warning в лог контейнера и выбрасывает условие, то есть бот
входит по более слабым условиям, чем настроил пользователь.

1. **[multifilter_strategy.template](../../backend/src/templates/multifilter_strategy.template)**
   — добавить расчёт в `compute_indicators()` (она вызывается и для базового
   таймфрейма, и для каждого информативного — с суффиксом) и имя колонки в
   `INDICATOR_COLUMNS`, по которому идут и `merge_informative_pair`, и переименование
   `ind_tf_tf → ind_tf`. Периоды задаются константами там же.
2. **[schemas/bot.py](../../backend/src/schemas/bot.py)** — расширить
   `FilterRule.indicator`. Без этого фильтр не пройдёт валидацию; и здесь же проходит
   защита от подстановки произвольного кода в шаблон.
3. **Ассистент и фронтенд** — `_INDICATORS` в
   [services/assistant/tools.py](../../backend/src/services/assistant/tools.py),
   описание шкалы в [prompt.py](../../backend/src/services/assistant/prompt.py) и
   `INDICATOR_META` в `frontend/lib/constants.ts` (подпись, период, справка,
   значение по умолчанию — выпадающий список формы и карточка бота строятся по нему).
4. **Тесты** —
   [test_strategy_template_indicators.py](../../backend/tests/unit/test_strategy_template_indicators.py)
   сцепляет схему, шаблон и ассистента: новый индикатор просто добавляется в три
   места, и тест либо сходится, либо показывает, какое из них забыли.

Индикатор должен считаться из тех колонок, что уже есть в датафрейме
(`open/high/low/close/volume`), иначе понадобится ещё и загрузка новых данных.
Если у индикатора своя шкала (как у %B — доля от 0 до 1), приводите её к тому же
виду, что у остальных: значение вводится обычным числом в одно и то же поле формы.

---

## Добавить новое поле настройки

Полный путь поля от формы до бота. Пропуск любого шага даёт молчаливую потерю
значения — ровно это и случилось с трейлингом: переключатель в форме был, а поля в
`BotCreate` не было, и до бота ничего не доезжало. Переключатель в итоге убрали
(`a27beab`), а не дотянули — см. [README](README.md#трейлинг-с-дефолтными-константами-убыточен).

| Шаг | Файл | Что сделать |
|---|---|---|
| 1 | `frontend/app/bot-creation/page.tsx` | Положить поле в `payload` |
| 2 | `frontend/lib/types.ts` | Добавить в тип `BotCreatePayload` |
| 3 | `backend/src/schemas/bot.py` | Добавить в `BotCreate` со строгим типом |
| 4 | `backend/src/models/bot.py` | Колонка в модели |
| 5 | `backend/alembic/` | `alembic revision --autogenerate`, прочитать глазами |
| 6 | `backend/src/services/bot_service.py` | Передать из `body` в `Bot(...)` |
| 7 | `backend/src/services/bot_file_manager.py` | Передать в генератор |
| 8 | `freqtrade_config.py` или `freqtrade_strategy.py` | Проставить в конфиг/шаблон |
| 9 | шаблон | Placeholder `{{...}}` или ключ JSON |
| 10 | тесты | Юнит-тест на генератор |

Шаг 10 не формальность: тест обязан быть **показан красным** — сломайте строку,
которую он покрывает, убедитесь, что упал, верните. Раскладка чисел по ключам
freqtrade — тот класс ошибки, который тесты ловят, а глаз нет: freqtrade молча
принимает любое число в любом ключе.

Если поле — процент от цены (как TP и SL), ему нужен ещё и перевод в доли маржи в
`BotService`, и граница в `BotCreate`, чтобы `× leverage` не вышло за пределы,
которые принимает freqtrade.

---

## Проверить, что сгенерируется, не создавая бота

Быстрее, чем поднимать контейнер:

```bash
cd backend
python - <<'EOF'
import asyncio
from src.services.bot_service import BotService
from src.services.freqtrade_config import generate_config
from src.services.freqtrade_strategy import generate_strategy_file

async def main():
    cfg = await generate_config(
        pair="ETH/USDT:USDT", api_port_inside_container=8080,
        jwt_secret="j", ws_token="w", api_username="u", api_password="p",
        exchange_key="", exchange_secret="",
        deposit=100.0, stake_ratio=0.2, user_id=1, dry_run=True,
    )
    print("ставка:", cfg["stake_amount"],
          "кошелёк:", cfg["dry_run_wallet"],
          "капитал:", cfg["available_capital"])

    # take_profit/stoploss здесь — уже ДОЛИ МАРЖИ, как их кладёт BotService.
    # Для «TP 1.5% цены при x10» это 0.15, а не 0.015.
    leverage = 10
    take_profit = BotService._build_take_profit(1.5, leverage)      # {"0": 0.15}
    stoploss = BotService._build_stoploss(True, 1.0, leverage)      # -0.1

    code = generate_strategy_file(
        leverage=leverage, can_short=False,
        entry_filters_long=[{"indicator": "rsi", "timeframe": "5m",
                             "condition": "less", "value": 50}],
        entry_filters_short=[],
        take_profit=take_profit, stoploss=stoploss, trailing_stop=False,
    )
    print(code.split("class MultiFilterStrategy")[0][-500:])

asyncio.run(main())
EOF
```

---

## Посчитать, что настройки значат в деньгах

Тот же расчёт, что показывает форма на шаге 4 — если надо проверить его руками или
прикинуть настройки до создания бота. Логика один в один с
[tradeMath.ts](../../frontend/app/bot-creation/tradeMath.ts); держите их в согласии,
если правите.

```bash
python - <<'EOF'
tp, sl, lev = 1.5, 1.0, 10   # проценты ДВИЖЕНИЯ ЦЕНЫ из формы и плечо
margin = 20.0                # депозит на одну сделку, USDT
fee = 0.06                   # комиссия за круг, % от цены

print(f"уедет во freqtrade:  minimal_roi {{'0': {tp/100*lev:.4f}}}, stoploss {-sl/100*lev:.4f}")
print(f"комиссия:            {fee*lev:.2f}% маржи")
print(f"выигрыш:             +{tp*lev:.2f}% маржи = {margin*tp*lev/100:+.2f} USDT")
print(f"проигрыш:            -{(sl+fee)*lev:.2f}% маржи = {-margin*(sl+fee)*lev/100:.2f} USDT")
print(f"цена до TP:          {tp+fee:.2f}%   (цель + комиссия)")
print(f"цена до стопа:       {sl+fee:.2f}%")
print(f"нужный винрейт:      {100*(sl+fee)/(tp+sl+fee):.0f} сделок из 100")
print(f"до ликвидации:       ~{100/lev:.1f}% движения цены")
EOF
```

Три проверки, которые стоит делать глазами:

- **Винрейт не должен зависеть от плеча.** Подставьте x1 и x25 — число обязано
  остаться тем же. Если изменилось, где-то потерялось или задвоилось умножение.
- **`sl × lev` должен быть меньше 100**, иначе `BotCreate` отобьёт настройку: стоп
  съедает всю маржу.
- **TP меньше пяти комиссий (0.3% цены)** — форма покажет предупреждение, и оно по делу.

---

## Понять, по какой трактовке TP/SL работает старый бот

До коммита `5e1efd8` проценты уезжали во freqtrade без умножения на плечо, а файлы
бота генерируются один раз. Значит бот, созданный раньше, до сих пор торгует по старым
числам, и его настройки нельзя читать так же, как у нового.

```bash
grep -E "TAKE_PROFIT|STOPLOSS|LEVERAGE" \
     bots_data/<bot_id>/user_data/strategies/MultiFilterStrategy.py
```

```
LEVERAGE = 10
TAKE_PROFIT = {'0': 0.015}    # старая трактовка: 1.5% МАРЖИ = 0.15% цены
TAKE_PROFIT = {'0': 0.15}     # новая:            15% маржи = 1.5% цены
```

Правило чтения: разделите `TAKE_PROFIT` на `LEVERAGE` — получите движение цены. Если
вышли сотые доли процента (меньше комиссии), это бот старой трактовки, и его цели
лежат внутри спреда. Лечится только пересозданием, см.
[рецепт выше](#применить-починку-к-уже-работающему-боту).

## Отладка: симптом → причина

| Симптом | Вероятная причина | Что смотреть |
|---|---|---|
| Бот `running`, но сделок нет вообще | `stake_amount > available_capital` — freqtrade не может открыть позицию и молчит | `docker logs <c> \| grep -i "insufficient\|not enough\|Available balance"` |
| Сделок нет, но и ошибок нет | Фильтры никогда не выполняются одновременно (они через И) | `/api/v1/show_config`, потом посчитать индикаторы руками |
| Сделок подозрительно много | Фильтр вида «RSI < 90» истинен почти всегда + вход на каждой новой свече | `entry_filters_long` в базе |
| Сделок много, а фильтры выглядят строгими | Колонки индикатора нет в датафрейме — фильтр молча снят, осталось только `volume > 0` | `docker logs <c> \| grep "не найдена"` |
| TP/SL срабатывают в десять раз ближе, чем задано | Бот создан до `5e1efd8` и работает по старой трактовке | [рецепт](#понять-по-какой-трактовке-tpsl-работает-старый-бот) |
| Бот в `error`, сообщение `Freqtrade stopped trading (state: stopped)` | Процесс жив, торговый цикл встал по `OperationalException` | `docker logs <c> \| grep -i "operational\|exception"` |
| Контейнер не стартует, в логах права на файлы | `chown 1000:1000` не отработал: бэкенд не владелец папки бота | `ls -la bots_data/<bot_id>` |
| Новый бот не создаётся, хотя всё заполнено | `stop_loss_percent × leverage >= 100` — стоп съедает маржу | Текст ошибки от `BotCreate`, он называет максимум для этого плеча |
| Сделки закрываются через 5–6 секунд с `emergency_exit` | Биржа не приняла стоп-ордер, freqtrade вышел рынком | `docker logs <c> \| grep -i "emergency\|stoploss"` |
| Убыток по стопу больше заданного | Норма: комиссия × плечо | [README](README.md#отсюда--асимметрия-tp-и-sl) |
| Прибыль по `roi` больше заданного TP | Норма: цена проскочила цель внутри свечи | |
| Бот стартовал и сразу умер | Битый `config.json` или стратегия не компилируется | `docker logs <c> \| head -50` — freqtrade падает до подъёма REST API, но `/bots/{id}/logs` читает docker и тоже покажет причину |
| `Bot API is not responding for 90 seconds` | Контейнер жив, но REST API не отвечает | `docker ps -a`, затем логи |
| Плечо в сделках меньше заданного | Биржа ограничила: `leverage()` возвращает `min(заданное, max_leverage)` | логи контейнера |
| Изменил шаблон — на боте не применилось | Файлы генерируются один раз при создании | [рецепт выше](#применить-починку-к-уже-работающему-боту) |

Полезные команды:

```bash
docker ps -a --filter name=bot_                    # все контейнеры ботов
docker logs --tail 100 <container_name>            # последние строки
docker logs <container_name> 2>&1 | grep -i error
docker stats --no-stream <container_name>          # упёрся ли в mem_limit 512m
docker network inspect cryptobot-network           # все ли боты в сети
```

Со стороны бэкенда те же события видно в логах приложения — воркер пишет туда каждый
промах ping:

```bash
grep -i "not responding\|stopped working\|Failed to fetch" backend/logs/app.log | tail -20
```

---

## Чек-лист перед правкой шаблонов

- [ ] Понимаю, в чём измеряется значение: пользователь вводит **движение цены**,
      freqtrade считает **от маржи**, между ними умножение на плечо в `BotService`?
- [ ] Проверил на крайних плечах (x1 и x125) — значение не выродилось в доли процента
      движения цены и не вышло за `stoploss <= -1`?
- [ ] Новое значение проходит через `Literal`/`Field` в Pydantic? Всё, что попадает
      в шаблон стратегии, исполняется как Python внутри контейнера.
- [ ] `config.template.json` остался валидным JSON (`python -m json.tool`)?
- [ ] Есть юнит-тест, и он показан красным?
- [ ] `python -m pytest` и `ruff check .` зелёные?
- [ ] Понятно, что на уже созданных ботов правка не подействует — и решено, что с
      ними делать?
- [ ] Если менялся шаблон стратегии — сгенерированный файл компилируется?
      (`python -c "import ast; ast.parse(open(path, encoding='utf-8').read())"`)
