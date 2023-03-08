from __future__ import annotations

import logging
import os
import pathlib

import rich.traceback
import rtoml
from pydantic import (BaseModel, BaseSettings, Field,
                      ValidationError, validator)
from pydantic.env_settings import SettingsSourceCallable
from rich import print
from rich.panel import Panel

from patchwork.settings import dotenv_settings_file, user_settings_file

logger = logging.getLogger("proxima")
rich.traceback.install(show_locals=False)


def load_toml_user(_):
    user_toml = pathlib.Path(user_settings_file)
    return rtoml.load(user_toml.read_text())


class App(BaseModel):
    loglevel: str = Field(
        ...,
        description="General application loglevel",
    )
    render_directory: str = Field(
        ...,
        description="Root directory for rendered files and sidecars",
    )

    @validator("loglevel")
    def must_be_valid_loglevel(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(
                f"'{v}' is not a valid loglevel. "
                f"Choose from [cyan]{', '.join(valid_levels)}[/]"
            )
        return v

    @validator("render_directory")
    def dir_is_writable(cls, v):
        if not os.path.exists(v):
            raise FileNotFoundError(
                f"Render directory '{v}' does not exist! "
                "Please create the directory or pick another one."
            )

        if not os.access(v, os.W_OK):
            raise PermissionError(
                f"Render directory '{v}' is unwritable! "
                "Please change permissions or pick another directory."
            )
        return v


class Render(BaseModel):
    allow_generic_render_presets: bool = Field(
        ..., description="Allow rendering with a non-custom render preset"
    )


class Advanced(BaseModel):
    advanced_stuff: bool = Field(
        ..., description="Ffmpeg's internal loglevel visible in worker output"
    )


class Settings(BaseSettings):
    app: App
    render: Render
    advanced: Advanced

    class Config:
        env_file = dotenv_settings_file
        env_file_encoding = "utf-8"
        env_prefix = "PATCHWORK"
        env_nested_delimiter = "__"

        @classmethod
        def customise_sources(
            cls,
            init_settings,
            env_settings,
            file_secret_settings,
        ) -> tuple[SettingsSourceCallable, ...]:
            return (
                env_settings,
                load_toml_user,
                file_secret_settings,
                init_settings,
            )


settings = None


try:
    settings = Settings()  # type: ignore
except ValidationError as e:
    print(
        Panel(
            title="[red]Uh, oh! Invalid user settings",
            title_align="left",
            highlight=True,
            expand=False,
            renderable=f"\n{str(e)}\n\nRun 'Proxima config --help' "
                        "to see how to fix broken settings.",
        )
    )
    exit()

if __name__ == "__main__":
    if settings:
        print(settings.dict())
