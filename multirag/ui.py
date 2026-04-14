from __future__ import annotations

from dataclasses import dataclass

from colorama import Fore, Style, init


@dataclass(frozen=True)
class UIOptions:
    """Define el comportamiento visual de la CLI para distintos entornos."""

    use_color: bool = True
    use_progress: bool = True


class CliUI:
    """Centraliza mensajes de terminal para mantener salida consistente y clara."""

    def __init__(self, options: UIOptions) -> None:
        """Inicializa opciones de interfaz y prepara colorama para la sesion."""

        self.options = options
        init(autoreset=True)

    def title(self, text: str) -> None:
        """Resalta secciones principales para estructurar la salida de consola."""

        print(self._paint(f"\n== {text} ==", Fore.CYAN))

    def info(self, text: str) -> None:
        """Comunica informacion de progreso sin indicar exito o error."""

        print(self._paint(f"[INFO] {text}", Fore.BLUE))

    def ok(self, text: str) -> None:
        """Muestra confirmaciones de pasos completados correctamente."""

        print(self._paint(f"[OK] {text}", Fore.GREEN))

    def warn(self, text: str) -> None:
        """Advierte situaciones recuperables que requieren atencion del usuario."""

        print(self._paint(f"[WARN] {text}", Fore.YELLOW))

    def error(self, text: str) -> None:
        """Informa fallos que impiden completar la accion solicitada."""

        print(self._paint(f"[ERROR] {text}", Fore.RED))

    def dim(self, text: str) -> str:
        """Atenua texto auxiliar para diferenciarlo del contenido principal."""

        return self._paint(text, Style.DIM)

    def score(self, value: float) -> str:
        """Presenta puntuaciones de similitud con color segun su relevancia."""

        if value >= 0.8:
            color = Fore.GREEN
        elif value >= 0.55:
            color = Fore.CYAN
        elif value >= 0.35:
            color = Fore.YELLOW
        else:
            color = Fore.RED
        return self._paint(f"{value:.4f}", color)

    def _paint(self, text: str, color: str) -> str:
        """Aplica color condicional segun configuracion para formatear la salida."""

        if not self.options.use_color:
            return text
        return f"{color}{text}{Style.RESET_ALL}"
