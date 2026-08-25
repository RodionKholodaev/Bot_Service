# Рецепты: freqtrade в Bot_Service

Типовые задачи по шагам. Что означают сами настройки — в [README.md](README.md).

Команды бэкенда — из папки `backend/`, команды с `docker` — на сервере.

---

## Оглавление

- [Посмотреть, с какими настройками реально работает бот](#посмотреть-с-какими-настройками-реально-работает-бот)
- [Изменить настройку в конфиге для всех новых ботов](#изменить-настройку-в-конфиге-для-всех-новых-ботов)
- [Применить починку к уже работающему боту](#применить-починку-к-уже-работающему-боту)
- [Добавить новый индикатор](#добавить-новый-индикатор)
- [Добавить новое поле настройки](#добавить-новое-поле-настройки)
- [Проверить, что сгенерируется, не создавая бота](#проверить-что-сгенерируется-не-создавая-бота)
- [Пересчитать проценты в движение цены](#пересчитать-проценты-в-движение-цены)
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

Сейчас поддерживаются только `rsi` и `cci`. Продуктовое правило проекта — простота,
так что сначала стоит спросить, точно ли индикатор нужен. Если да, трогать придётся
четыре места:

1. **[multifilter_strategy.template](../../backend/src/templates/multifilter_strategy.template)**,
   `populate_indicators()` — посчитать индикатор для базового таймфрейма **и** для
   каждого информативного, плюс добавить его в список колонок, которые уезжают в
   `merge_informative_pair`, и в цикл переименования `for ind in ["rsi", "cci"]`.
2. **[schemas/bot.py](../../backend/src/schemas/bot.py)** — расширить
   `FilterRule.indicator: Literal["rsi", "cci"]`. Без этого фильтр не пройдёт
   валидацию; и здесь же проходит защита от подстановки произвольного кода в шаблон.
3. **Фронтенд** — список индикаторов в форме создания бота.
4. **Тесты** — на генерацию стратегии.

Индикатор должен считаться из тех колонок, что уже есть в датафрейме
(`open/high/low/close/volume`), иначе понадобится ещё и загрузка новых данных.

---

## Добавить новое поле настройки

Полный путь поля от формы до бота — на примере трейлинга, который сейчас именно на
этом пути и теряется:

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

Пропуск любого шага даёт ровно тот эффект, что и с трейлингом: в интерфейсе
переключатель есть, в базе всегда `False`, до бота ничего не доезжает и никто не
замечает.

---

## Проверить, что сгенерируется, не создавая бота

Быстрее, чем поднимать контейнер:

```bash
cd backend
python - <<'EOF'
import asyncio
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

    code = generate_strategy_file(
        leverage=10, can_short=False,
        entry_filters_long=[{"indicator": "rsi", "timeframe": "5m",
                             "condition": "less", "value": 50}],
        entry_filters_short=[],
        take_profit={"0": 0.015}, stoploss=-0.01, trailing_stop=False,
    )
    print(code.split("class MultiFilterStrategy")[0][-500:])

asyncio.run(main())
EOF
```

---

## Пересчитать проценты в движение цены

Считает то, что пользователь на самом деле настроил. Пригодится и для предупреждений
в интерфейсе.

```bash
python - <<'EOF'
tp, sl, lev = 1.5, 1.0, 10        # проценты из формы и плечо
fee = 0.06                        # комиссия за круг, % от объёма позиции

print(f"вход по TP:  цена должна пройти {tp/lev:.3f}%")
print(f"вход по SL:  цена должна пройти {sl/lev:.3f}%")
print(f"комиссия:    {fee*lev:.2f}% от маржи")
sl_real = sl + fee*lev
print(f"реальный SL: -{sl_real:.2f}% вместо -{sl:.2f}%")
print(f"нужный винрейт: {100*sl_real/(tp+sl_real):.0f} сделок из 100")
EOF
```

---

## Отладка: симптом → причина

| Симптом | Вероятная причина | Что смотреть |
|---|---|---|
| Бот `running`, но сделок нет вообще | `stake_amount > available_capital` — freqtrade не может открыть позицию и молчит | `docker logs <c> \| grep -i "insufficient\|not enough\|Available balance"` |
| Сделок нет, но и ошибок нет | Фильтры никогда не выполняются одновременно (они через И) | `/api/v1/show_config`, потом посчитать индикаторы руками |
| Сделок подозрительно много | Фильтр вида «RSI < 90» истинен почти всегда + вход на каждой новой свече | `entry_filters_long` в базе |
| Сделки закрываются через 5–6 секунд с `emergency_exit` | Биржа не приняла стоп-ордер, freqtrade вышел рынком | `docker logs <c> \| grep -i "emergency\|stoploss"` |
| Убыток по стопу больше заданного | Норма: комиссия × плечо | [README](README.md#отсюда--асимметрия-tp-и-sl) |
| Прибыль по `roi` больше заданного TP | Норма: цена проскочила цель внутри свечи | |
| Бот стартовал и сразу умер | Битый `config.json` или стратегия не компилируется | `docker logs <c> \| head -50` — freqtrade падает до подъёма REST API, наш `/bots/{id}/logs` тут не поможет |
| `Bot API is not responding for 90 seconds` | Контейнер жив, но REST API не отвечает | `docker ps -a`, затем логи |
| Плечо в сделках меньше заданного | Биржа ограничила: `leverage()` возвращает `min(заданное, max_leverage)` | логи контейнера |
| Изменил шаблон — на боте не применилось | Файлы генерируются один раз при создании | [рецепт выше](#применить-починку-к-уже-работающему-боту) |

Полезные команды:

```bash
docker ps -a --filter name=bot_                    # все контейнеры ботов
docker logs --tail 100 <container_name>            # последние строки
docker logs <container_name> 2>&1 | grep -i error
docker stats --no-stream <container_name>          # упёрся ли в mem_limit 512m
```

---

## Чек-лист перед правкой шаблонов

- [ ] Понимаю, что настройка задаётся **от маржи с учётом плеча**, а не от цены?
- [ ] Проверил на крайних плечах (x1 и x15) — не превращается ли значение в доли
      процента движения цены?
- [ ] Новое значение проходит через `Literal`/`Field` в Pydantic? Всё, что попадает
      в шаблон стратегии, исполняется как Python внутри контейнера.
- [ ] `config.template.json` остался валидным JSON (`python -m json.tool`)?
- [ ] Есть юнит-тест, и он показан красным?
- [ ] `python -m pytest` и `ruff check .` зелёные?
- [ ] Понятно, что на уже созданных ботов правка не подействует — и решено, что с
      ними делать?
