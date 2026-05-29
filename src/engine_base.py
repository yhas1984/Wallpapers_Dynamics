from abc import ABC, abstractmethod


class BaseWallpaperEngine(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        ...

    @property
    @abstractmethod
    def current_video(self) -> str | None:
        ...

    @property
    def is_paused(self) -> bool:
        return False

    @abstractmethod
    def start(self, video_path: str, **kwargs) -> bool:
        ...

    @abstractmethod
    def stop(self):
        ...

    @abstractmethod
    def cleanup(self):
        ...

    def pause(self):
        pass

    def set_mute(self, muted: bool):
        pass

    def set_volume(self, volume: int):
        pass

    def set_brightness(self, val: int):
        pass

    def set_contrast(self, val: int):
        pass

    def set_blur(self, val: int):
        pass

    def update_filters(self, filters: dict):
        pass

    def set_fps(self, fps: int):
        pass

    def hide(self):
        pass

    def show(self):
        pass
