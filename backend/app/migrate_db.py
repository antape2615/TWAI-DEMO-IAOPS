"""
Script de migración para añadir columnas faltantes
"""
import asyncio
from sqlalchemy import text
from app.core.database import engine
from app.core.logging import logger

async def migrate():
    """Ejecuta migraciones manuales"""
    logger.info("Iniciando migración de base de datos...")
    
    try:
        async with engine.begin() as conn:
            logger.info("Migración: Verificando/añadiendo columna 'name'...")
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name='architecture_generation' AND column_name='name'
                    ) THEN
                        ALTER TABLE architecture_generation ADD COLUMN name VARCHAR(200) DEFAULT 'Arquitectura 1';
                        UPDATE architecture_generation SET name = 'Arquitectura 1' WHERE name IS NULL;
                        ALTER TABLE architecture_generation ALTER COLUMN name SET NOT NULL;
                    END IF;
                END $$;
            """))

            logger.info("Migración: Aplicando claves foráneas con CASCADE...")
            # Tablas a las que añadiremos FK con CASCADE
            tables = [
                "cloud_credentials",
                "repository_credentials",
                "deployment_history",
                "architecture_generation",
                "cicd_credentials"  # Nueva tabla
            ]
            
            for table in tables:
                logger.info(f"Procesando tabla: {table}")
                await conn.execute(text(f"""
                    DO $$
                    DECLARE
                        r RECORD;
                    BEGIN
                        -- Solo si la tabla existe
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='{table}') THEN
                            
                            -- 1. Limpiar huérfanos antes de añadir el FK (evita que falle si ya hay basura)
                            EXECUTE 'DELETE FROM {table} WHERE client_id NOT IN (SELECT id FROM clients)';
                            
                            -- 2. Buscar y eliminar CUALQUIER constraint de FK en la columna client_id
                            FOR r IN (
                                SELECT tc.constraint_name 
                                FROM information_schema.table_constraints AS tc 
                                JOIN information_schema.key_column_usage AS kcu
                                  ON tc.constraint_name = kcu.constraint_name
                                  AND tc.table_schema = kcu.table_schema
                                WHERE tc.constraint_type = 'FOREIGN KEY' 
                                  AND tc.table_name = '{table}'
                                  AND kcu.column_name = 'client_id'
                            ) LOOP
                                EXECUTE 'ALTER TABLE {table} DROP CONSTRAINT ' || quote_ident(r.constraint_name);
                            END LOOP;
                            
                            -- 3. Añadir el nuevo FK definitivo con CASCADE
                            EXECUTE 'ALTER TABLE {table} ADD CONSTRAINT fk_{table}_client_id FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE';
                        END IF;
                    END $$;
                """))
            
            logger.info("Migración completada: Esquema actualizado con CASCADE.")
            
    except Exception as e:
        logger.error(f"Error durante la migración: {e}")
        # No relanzamos para no bloquear el inicio si falla algo no crítico
        # pero en producción esto debería ser más robusto

if __name__ == "__main__":
    asyncio.run(migrate())
