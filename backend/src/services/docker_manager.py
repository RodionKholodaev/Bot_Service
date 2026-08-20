"""
Docker-менеджер — тонкая обёртка над Docker SDK.

Все операции с контейнерами (создать, запустить, остановить, удалить, прочитать логи)
изолированы здесь. Если завтра захочешь переехать на docker-compose, podman или k8s —
менять надо будет только этот файл.
"""

import logging
import os
import platform
from pathlib import Path

import docker
from docker.errors import APIError, ImageNotFound, NotFound
from docker.models.containers import Container

from src.config import settings

logger = logging.getLogger(__name__)


# Внутри контейнера freqtrade всегда слушает 8080 (так задано в шаблоне config).
# Снаружи мы пробрасываем этот порт на уникальный bot.api_port.
INTERNAL_API_PORT = 8080


def set_bot_permissions(bot_data_dir: Path) -> None:
    """
    Делает владельцем папки бота пользователя UID=1000 (ftuser в контейнере).

    Аналог:
        chown -R 1000:1000 <bot_data_dir>
    """

    uid = 1000
    gid = 1000

    logger.info(
        "Updating bot directory ownership",
        extra={
            "bot_directory": str(bot_data_dir),
            "uid": uid,
            "gid": gid,
        },
    )

    if platform.system() == "Windows":
        logger.debug(
            "Skipping ownership update on Windows",
            extra={
                "bot_directory": str(bot_data_dir),
            },
        )
        return

    chown = getattr(os, "chown", None)

    if chown is None:
        logger.warning(
            "Ownership update skipped because os.chown is unavailable",
            extra={
                "bot_directory": str(bot_data_dir),
            },
        )
        return

    try:
        chown(bot_data_dir, uid, gid)

        for path in bot_data_dir.rglob("*"):
            chown(path, uid, gid)

        logger.info(
            "Bot directory ownership updated successfully",
            extra={
                "bot_directory": str(bot_data_dir),
                "uid": uid,
                "gid": gid,
            },
        )

    except PermissionError:
        logger.exception(
            "Failed to update bot directory ownership",
            extra={
                "bot_directory": str(bot_data_dir),
                "uid": uid,
                "gid": gid,
            },
        )
        raise


def get_client() -> docker.DockerClient:
    """Получает Docker-клиент. На Windows работает с Docker Desktop из коробки."""
    return docker.from_env()


def ensure_network(name: str = settings.DOCKER_NETWORK_NAME) -> None:
    """Создаёт Docker-сеть, если её ещё нет. Вызывается при старте приложения."""
    client = get_client()
    try:
        client.networks.get(name)
        logger.info(
            "Docker network already exists",
            extra={
                "network_name": name,
            },
        )
    except NotFound:
        client.networks.create(name, driver="bridge")
        logger.info(
            "Docker network created",
            extra={
                "network_name": name,
            },
        )


def ensure_image(image: str = settings.FREQTRADE_IMAGE) -> None:
    """
    Проверяет, что образ freqtrade есть локально. Если нет — пытается стянуть.
    """
    client = get_client()
    try:
        client.images.get(image)
    except ImageNotFound:
        logger.info("Image wasn't found locally, pulling it from the registry", extra={"image": image})
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

    logger.info(
        "Starting bot container",
        extra={
            "container_name": container_name,
            "image": image,
            "network": network_name,
            "api_port": api_port_external,
            "bot_directory": str(bot_data_dir),
        },
    )

    client = get_client()

    try:
        old = client.containers.get(container_name)

        logger.warning(
            "Existing container found. Recreating container",
            extra={
                "container_name": container_name,
            },
        )

        try:
            logger.debug(
                "Stopping existing container",
                extra={
                    "container_name": container_name,
                },
            )
            old.stop(timeout=5)
        except APIError:
            logger.exception(
                "Failed to stop existing container",
                extra={
                    "container_name": container_name,
                },
            )

        logger.debug(
            "Removing existing container",
            extra={
                "container_name": container_name,
            },
        )
        old.remove(force=True)

    except NotFound:
        logger.debug(
            "Existing container not found",
            extra={
                "container_name": container_name,
            },
        )

    host_dir_path = bot_data_dir.resolve()

    set_bot_permissions(host_dir_path)

    host_dir = str(host_dir_path)

    try:
        logger.debug(
            "Creating Docker container",
            extra={
                "container_name": container_name,
                "image": image,
            },
        )

        container = client.containers.run(
            image=image,
            name=container_name,
            detach=True,
            network=network_name,
            ports={
                f"{INTERNAL_API_PORT}/tcp": api_port_external,
            },
            volumes={
                host_dir: {
                    "bind": "/freqtrade/user_data_mount",
                    "mode": "rw",
                },
            },
            command=[
                "trade",
                "--config",
                "/freqtrade/user_data_mount/config.json",
                "--strategy",
                "MultiFilterStrategy",
                "--strategy-path",
                "/freqtrade/user_data_mount/user_data/strategies",
                "--datadir",
                "/freqtrade/user_data_mount/user_data/data",
                "--db-url",
                "sqlite:////freqtrade/user_data_mount/user_data/tradesv3.sqlite",
            ],
            restart_policy={"Name": "on-failure", "MaximumRetryCount": 5},
            mem_limit="512m",
        )  # type: ignore

    except APIError:
        logger.exception(
            "Failed to start bot container",
            extra={
                "container_name": container_name,
                "image": image,
                "network": network_name,
                "api_port": api_port_external,
                "bot_directory": host_dir,
            },
        )
        raise

    logger.info(
        "Bot container started successfully",
        extra={
            "container_name": container_name,
            "container_id": container.id,
            "container_short_id": container.short_id,
            "image": image,
            "network": network_name,
            "api_port": api_port_external,
        },
    )

    return container


def stop_container(container_id: str) -> None:
    client = get_client()
    try:
        c = client.containers.get(container_id)
        c.stop(timeout=10)
        logger.info(
            "Container stopped successfully",
            extra={
                "container_id": container_id,
            },
        )
    except NotFound:
        logger.warning("Container wasn't found during stop, continue", extra={"container_id": container_id})


def remove_container(container_id: str) -> None:
    client = get_client()
    logger.info("Starting to remove container", extra={"container_id": container_id})
    try:
        c = client.containers.get(container_id)
        try:
            c.stop(timeout=5)
        except APIError:
            logger.error("Couldn't contact to the container", extra={"container_id": container_id})
        c.remove(force=True)
        logger.info(
            "Container was successfully removed",
            extra={"container_id": container_id},
        )
    except NotFound:
        logger.warning("Container has already been removed", extra={"container_id": container_id})


def get_container_status(container_id: str) -> str | None:
    """
    Возвращает статус контейнера ('running', 'exited', 'created', ...) или None,
    если контейнер не существует.
    """
    client = get_client()
    try:
        c = client.containers.get(container_id)
        return c.status
    except NotFound as e:
        logger.warning("Couldn't find the container", extra={"container_id": container_id, "error": str(e)})


def get_container_logs(container_id: str, tail: int = 200) -> str:
    """Возвращает последние tail строк логов контейнера."""
    client = get_client()
    try:
        c = client.containers.get(container_id)
        return c.logs(tail=tail).decode("utf-8", errors="replace")

    except NotFound as e:
        logger.warning("Couldn't find the container", extra={"container_id": container_id, "error": str(e)})
        return ""
