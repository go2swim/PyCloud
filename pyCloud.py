import os
import re
import click
import src.clouds_manager

from src.clouds_manager import (
    sync_folders,
    get_and_update_sync_folders,
    save_sync_folders,
    ROOT_FOLDER,
    sync_locals_folders,
    CLOUDS,
)


def validate_folder_path(ctx, param, value):
    """Проверяет, существует ли путь, и является ли он папкой."""
    if not os.path.exists(value):
        raise click.BadParameter(f"Путь {value} не существует.")
    if not os.path.isdir(value):
        raise click.BadParameter(f"Путь {value} не является папкой.")
    return value


def validate_cloud_path(ctx, param, value):
    if ROOT_FOLDER not in value:
        raise click.BadParameter(
            f"Путь {value} должен начинаться или содержать в себе {ROOT_FOLDER}."
        )
    if "/" in value and "\\" in value:
        raise click.BadParameter(
            f"Путь {value} не должен содержать разделителей разного типа."
        )

    path = re.search(rf"{ROOT_FOLDER}(?:/|\\)*.*", value)[0].replace("/", os.path.sep)
    if path.endswith(os.path.sep):
        path = path[:-1]

    return path


def validate_cloud_name(value, extension=False):
    value = int(value) - 1
    if extension:
        if value < 0 or value > len(CLOUDS) + 1:
            raise click.BadParameter(f"Пункта {value + 1} в меню нет")
    else:
        if value < 0 or value > len(CLOUDS):
            raise click.BadParameter(f"Пункта {value + 1} в меню нет")

    return value + 1

@click.group()
def pyCloud():
    pass


@pyCloud.command()
@click.argument("folder_full_path", callback=validate_cloud_path)
def list_files(folder_full_path):
    """Листинг файлов в главной папке"""

    cloud = get_clouds_menu()

    file_listings = src.clouds_manager.list_files(folder_full_path, [cloud])

    for folder, clouds_data in file_listings.items():
        click.echo(
            click.style(
                f"\n=== Содержимое папки: {folder} ===\n", fg="yellow", bold=True
            )
        )
        for cloud_name, files in clouds_data.items():
            click.echo(
                click.style(f"--- Облако: {cloud_name} ---", fg="blue", bold=True)
            )
            click.echo(
                click.style(
                    f"{'Тип':<10} {'Имя':<30} {'Размер':<15} {'Дата изменения':<20}",
                    fg="green",
                )
            )
            click.echo(click.style("-" * 80, fg="green"))
            for file in files:
                item_size = f"{file.item_size} bytes" if file.item_size else "-"
                item_modified = (
                    file.item_modified.strftime("%Y-%m-%d %H:%M:%S")
                    if file.item_modified
                    else "-"
                )
                click.echo(
                    f"{file.item_type:<10} {file.item_name:<30} {item_size:<15} {item_modified:<20}"
                )
            click.echo("\n")  # Разделитель между облаками


@pyCloud.command()
@click.argument("folder_full_path", callback=validate_folder_path)
def add_folder(folder_full_path):
    """Добавление новой папки в отслеживаемые"""
    save_sync_folders(folder_full_path)
    click.echo(f"Папка '{folder_full_path}' успешно добавлена в отслеживаемые.")


@pyCloud.command()
def watched_folders():
    """Вывод списка отслеживаемых папок"""
    folders = get_and_update_sync_folders()
    if folders:
        click.echo("Watched folders:")
        click.echo(", ".join(folders))


@pyCloud.command()
def sync_cloud():
    """Синхронизация пк -> облако"""
    clouds = get_clouds_menu()
    click.echo("Starting synchronization...")
    sync_folders(clouds)
    click.echo("Synchronization successfully")


@pyCloud.command()
def sync_pc():
    """Синхронизация облако -> пк"""
    cloud = get_clouds_menu()
    click.echo("Starting synchronization...")
    sync_locals_folders(cloud)
    click.echo("Synchronization successfully")

def get_clouds_menu():
    keys = list(CLOUDS.keys())
    clouds_with_keys = {i: keys[i - 1] for i in range(1, len(keys) + 1)}
    menu = "\n" + "\n".join([f"{k}: {v}" for k, v in clouds_with_keys.items()])
    number_in_menu = click.prompt(
        text="Выберите облако с которым вы хотите синхронизировать файлы на пк" + menu,
        value_proc=validate_cloud_name,
    )
    return clouds_with_keys[number_in_menu]

def get_valid_folder_path(folder_name):
    """Запрашивает у пользователя путь до папки и проверяет его на корректность."""
    path = click.prompt(
        text=f"На облаке обнаружена ранее отслеживаемая папка {folder_name}, введите новый абсолютный путь до неё",
        value_proc=lambda value: validate_folder_path(None, None, value),
    )
    full_path = f"{path}{os.path.sep}{folder_name}"
    save_sync_folders(full_path)
    return full_path  # путь не включает папку


if __name__ == "__main__":
    pyCloud()
    # sync_pc()
