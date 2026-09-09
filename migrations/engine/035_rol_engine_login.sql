-- =====================================================================
-- 035_rol_engine_login.sql  ·  habilitar LOGIN en catalaxia_engine
-- =====================================================================
-- F-025/011 creo el rol NOLOGIN y documento que la password se asigna
-- aparte, fuera del control de versiones. Consecuencia para un deploy
-- desde cero: la base limpia no arranca hasta el paso manual, y ese paso
-- hacia irreproducible un E2E "base limpia a la primera".
--
-- Esta migracion NO contiene secretos: solo habilita LOGIN. La password el
-- asigna por bootstrap administrativo en run_e2e_certified.py (ALTER ROLE
-- ... PASSWORD via engine con privilegio administrador, parametrizado y
-- nunca registrado en logs ni en el repo). Sin password el rol sigue sin
-- poder autenticarse: LOGIN sin password no abre la base.
--
-- Idempotente: ALTER ROLE con los mismos atributos es un no-op.
-- =====================================================================

DO $$
BEGIN
    ALTER ROLE catalaxia_engine WITH LOGIN;
END $$;