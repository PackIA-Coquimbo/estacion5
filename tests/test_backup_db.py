import sqlite3

from tools import backup_db


def test_backup_crea_copia_consistente(tmp_path, monkeypatch, capsys):
    base = tmp_path / "e5.db"
    with sqlite3.connect(base) as connection:
        connection.execute("CREATE TABLE muestra (valor TEXT)")
        connection.execute("INSERT INTO muestra VALUES ('lectura')")
    monkeypatch.setattr(backup_db, "DATABASE_PATH", base)

    resultado = backup_db.main(["--destino", str(tmp_path / "respaldos")])

    assert resultado == 0
    ruta = next((tmp_path / "respaldos").glob("e5-*.sqlite3"))
    with sqlite3.connect(ruta) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT valor FROM muestra").fetchone()[0] == "lectura"
    assert "Respaldo verificado" in capsys.readouterr().out


def test_backup_falla_si_no_existe_la_base(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_db, "DATABASE_PATH", tmp_path / "missing.db")
    try:
        backup_db.main(["--destino", str(tmp_path / "respaldos")])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("El comando debería rechazar una base inexistente")
