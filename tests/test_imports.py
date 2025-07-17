def test_import_db_session():
    from app.db import session
    assert hasattr(session, 'engine')
    assert hasattr(session, 'SessionLocal')

def test_import_grid_config():
    from app.models.grid_config import GridConfig
    assert hasattr(GridConfig, '__tablename__')

def test_import_init_db():
    import app.db.init_db
    assert hasattr(app.db.init_db, 'init_db') 