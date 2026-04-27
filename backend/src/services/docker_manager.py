"""
Docker-менеджер — тонкая обёртка над Docker SDK.

Все операции с контейнерами (создать, запустить, остановить, удалить, прочитать логи)
изолированы здесь. Если завтра захочешь переехать на docker-compose, podman или k8s —
менять надо будет только этот файл.
"""

import logging
from pathlib import Path

import docker
from docker.errors import APIError, NotFound, ImageNotFound
from docker.models.containers import Container

from src.config import settings

logger = logging.getLogger(__name__)


# Внутри контейнера freqtrade всегда слушает 8080 (так задано в шаблоне config).
# Снаружи мы пробрасываем этот порт на уникальный bot.api_port.
INTERNAL_API_PORT = 8080


def get_client() -> docker.DockerClient:
    """Получает Docker-клиент. На Windows работает с Docker Desktop из коробки."""
    return docker.from_env()


def ensure_network(name: str = settings.DOCKER_NETWORK_NAME) -> None:
    """Создаёт Docker-сеть, если её ещё нет. Вызывается при старте приложения."""
    client = get_client()
    try:
        client.networks.get(name)
        logger.info(f"Docker network '{name}' уже существует")
    except NotFound:
        client.networks.create(name, driver="bridge")
        logger.info(f"Создана Docker network '{name}'")


def ensure_image(image: str = settings.FREQTRADE_IMAGE) -> None:
    """
    Проверяет, что образ freqtrade есть локально. Если нет — пытается стянуть.
    На MVP ты должен заранее сделать `docker pull freqtradeorg/freqtrade:stable`,
    но эта функция страхует от случая, если образ ещё не скачан.
    """
    client = get_client()
    try:
        client.images.get(image)
    except ImageNotFound:
        logger.info(f"Образ {image} не найден локально, тяну из реестра...")
        client.images.pull(image)


def run_bot_container(
    container_name: str,
    bot_data_dir: Path,
    api_port_external: int,
    network_name: str = settings.DOCKER_NETWORK_NAME,
    image: str = settings.FREQTRADE_IMAGE,
) -> Container:
    """
    Запускает контейнер freqtrade для одного бота.

    bot_data_dir — папка на хосте, где лежат config.json и user_data/ этого бота.
    Она монтируется внутрь контейнера в /freqtrade/user_data_mount.

    api_port_external — порт на хосте, на который пробрасываем внутренний 8080.
    """
    client = get_client()

    # Убираем старый контейнер с тем же именем, если он есть (например, после краша).
    try:
        old = client.containers.get(container_name)
        logger.warning(f"Найден старый контейнер {container_name}, удаляю")
        try:
            old.stop(timeout=5)
        except APIError:
            pass
        old.remove(force=True)
    except NotFound:
        pass

    host_dir = str(bot_data_dir.resolve())

    container = client.containers.run(
        image=image,
        name=container_name,
        detach=True,
        network=network_name,
        ports={f"{INTERNAL_API_PORT}/tcp": api_port_external},
        volumes={
            host_dir: {"bind": "/freqtrade/user_data_mount", "mode": "rw"},
        },
        command=[
            "trade",
            "--config", "/freqtrade/user_data_mount/config.json",
            "--strategy", "MultiFilterStrategy",
            "--strategy-path", "/freqtrade/user_data_mount/user_data/strategies",
            "--datadir", "/freqtrade/user_data_mount/user_data/data",
            "--logfile", "/freqtrade/user_data_mount/user_data/logs/freqtrade.log",
            "--db-url", "sqlite:////freqtrade/user_data_mount/user_data/tradesv3.sqlite",
        ],
        restart_policy={"Name": "unless-stopped"}, #type: ignore
        mem_limit="512m",
    ) #type: ignore


    logger.info(f"Запущен контейнер {container_name} (id={container.short_id})")
    return container


def stop_container(container_id: str) -> None:
    client = get_client()
    try:
        c = client.containers.get(container_id)
        c.stop(timeout=10)
        logger.info(f"Остановлен контейнер {container_id}")
    except NotFound:
        logger.warning(f"Контейнер {container_id} не найден при остановке — пропускаю")


def remove_container(container_id: str) -> None:
    client = get_client()
    try:
        c = client.containers.get(container_id)
        try:
            c.stop(timeout=5)
        except APIError:
            pass
        c.remove(force=True)
        logger.info(f"Удалён контейнер {container_id}")
    except NotFound:
        logger.warning(f"Контейнер {container_id} уже удалён")


def get_container_status(container_id: str) -> str | None:
    """
    Возвращает статус контейнера ('running', 'exited', 'created', ...) или None,
    если контейнер не существует.
    """
    client = get_client()
    try:
        c = client.containers.get(container_id)
        return c.status
    except NotFound:
        return None


def get_container_logs(container_id: str, tail: int = 200) -> str:
    """Возвращает последние tail строк логов контейнера."""
    client = get_client()
    try:
        c = client.containers.get(container_id)
        return c.logs(tail=tail).decode("utf-8", errors="replace")
    except NotFound:
        return ""
