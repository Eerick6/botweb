"""Function calling tools for Taxiblau web bot.

Tools for taxi service:
  1. check_user_status — checks if user exists by phone number
  2. register_user — registers a new user with provided name and phone
  3. resolve_address — resolves a text address into validated coordinates
  4. create_taxi_service — creates the taxi service in backend/Laravel
"""

import os
from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams
from api_client import UsersAPIClient, AddressAPIClient, ServicesAPIClient, CallsAPIClient


def register_tools(llm, backend_url: str | None = None, calls_client: CallsAPIClient = None) -> ToolsSchema:
    """Register taxi service tools on the LLM for web.

    Args:
        llm: LLM service instance
        backend_url: URL of your backend
        calls_client: Cliente de calls para actualizar la llamada actual
    """

    if not backend_url:
        backend_url = os.getenv("BACKEND_URL", "http://localhost:3000")

    # Crear clientes para cada API
    users_client = UsersAPIClient(backend_url)
    address_client = AddressAPIClient(backend_url)
    services_client = ServicesAPIClient(backend_url)

    async def check_user_status(params: FunctionCallParams):
        """Verifica si un usuario existe usando su número de teléfono."""
        phone = (params.arguments.get("phone") or "").strip()
        logger.info(f"📞 Tool called: check_user_status(phone={phone!r})")

        if not phone:
            await params.result_callback({
                "success": False,
                "user_exists": False,
                "error": "Número de teléfono requerido",
                "message": "¿Podrías darme tu número de teléfono?",
            })
            return

        try:
            data = await users_client.check_user(phone)
            
            client = data.get("client")
            user_exists = data.get("user_exists", False)

            result = {
                "success": True,
                "user_exists": user_exists,
                "client_id": client.get("id") if client else None,
                "client_name": client.get("name") if client else None,
                "phone": phone.replace(" ", "").replace("-", "").replace("+", ""),
            }

            if user_exists and client and calls_client:
                await calls_client.assign_client(client.get("id"))
                logger.info(f"✅ Cliente {client.get('id')} asignado a llamada {calls_client.current_call_sid}")

            if user_exists and client:
                result["message"] = f"¡Hola de nuevo {client.get('name')}!"
            else:
                result["message"] = "No te tengo registrado. ¿Me dices tu nombre para crearte un perfil?"

            await params.result_callback(result)

        except Exception as e:
            logger.error(f"❌ Error en check_user_status: {e}")
            await params.result_callback({
                "success": False,
                "user_exists": False,
                "error": str(e),
                "message": "Tuve un problema verificando tu número. ¿Puedes intentar de nuevo?",
            })

    async def register_user(params: FunctionCallParams):
        """Registra un usuario nuevo con su número y nombre."""
        phone = (params.arguments.get("phone") or "").strip()
        name = (params.arguments.get("name") or "").strip()

        logger.info(f"📝 Tool called: register_user(phone={phone!r}, name={name!r})")

        if not phone:
            await params.result_callback({
                "success": False,
                "user_exists": False,
                "error": "Número de teléfono requerido",
                "message": "Necesito tu número de teléfono para registrarte.",
            })
            return

        if not name:
            await params.result_callback({
                "success": False,
                "user_exists": False,
                "error": "Nombre requerido",
                "message": "¿Me dices tu nombre completo para registrarte?",
            })
            return

        try:
            data = await users_client.register_user(phone, name)
            
            client = data.get("client")

            if client and calls_client:
                await calls_client.assign_client(client.get("id"))
                logger.info(f"✅ Nuevo cliente {client.get('id')} asignado a llamada {calls_client.current_call_sid}")

            await params.result_callback({
                "success": True,
                "user_exists": True,
                "client_id": client.get("id") if client else None,
                "client_name": name,
                "phone": phone,
                "message": f"¡Perfecto {name}! Ya quedaste registrado.",
            })

        except Exception as e:
            logger.error(f"❌ Error en register_user: {e}")
            await params.result_callback({
                "success": False,
                "user_exists": False,
                "error": str(e),
                "message": "Tuve un problema registrándote. ¿Puedes intentar de nuevo?",
            })

    async def resolve_address(params: FunctionCallParams):
        """Resuelve una dirección en texto libre a coordenadas."""
        query = (params.arguments.get("address_text") or "").strip()
        logger.info(f"📍 Tool called: resolve_address(address_text={query!r})")

        if not query:
            await params.result_callback({
                "success": False,
                "valid": False,
                "error": "Dirección requerida",
                "message": "¿Puedes repetir la dirección?",
            })
            return

        try:
            data = await address_client.resolve_address(query)

            if data.get("is_ambiguous"):
                data["message"] = "Necesito más detalles. ¿Puedes darme la calle y número?"
            elif data.get("valid"):
                formatted = data.get("formatted_address") or query
                data["message"] = f"¿Confirmas que es {formatted}?"
            else:
                data["message"] = "No encontré esa dirección. ¿Puedes ser más específico?"

            await params.result_callback(data)

        except Exception as e:
            logger.error(f"❌ Error en resolve_address: {e}")
            await params.result_callback({
                "success": False,
                "valid": False,
                "error": str(e),
                "message": "Tuve un problema validando la dirección. ¿Puedes repetirla?",
            })

    async def create_taxi_service(params: FunctionCallParams):
        """Crea un servicio de taxi."""
        args = params.arguments

        nest_client_id = args.get("nest_client_id")
        origin_address = args.get("origin_address")
        origin_locality = args.get("origin_locality")
        origin_latitude = args.get("origin_latitude")
        origin_longitude = args.get("origin_longitude")
        destination_address = args.get("destination_address")
        destination_locality = args.get("destination_locality")
        destination_latitude = args.get("destination_latitude")
        destination_longitude = args.get("destination_longitude")
        start_date = (args.get("start_date") or "").strip()

        people_number = int(args.get("people_number", 1))
        suitcases_number = int(args.get("suitcases_number", 0))
        vehicle_size_id = int(args.get("vehicle_size_id", 1))
        origin_postal_code = args.get("origin_postal_code") or ""
        destination_postal_code = args.get("destination_postal_code") or ""
        observations = args.get("observations") or ""
        is_transfer = bool(args.get("is_transfer", False))

        logger.info(f"🚕 Tool called: create_taxi_service(client_id={nest_client_id!r})")

        if not nest_client_id:
            await params.result_callback({
                "success": False,
                "error": "ID de cliente requerido",
                "message": "Falta el ID del cliente para crear el servicio.",
            })
            return

        if not start_date:
            await params.result_callback({
                "success": False,
                "error": "Fecha requerida",
                "message": "Necesito la fecha y hora del servicio.",
            })
            return

        try:
            payload = {
                "nest_client_id": nest_client_id,
                "callSid": calls_client.current_call_sid if calls_client else "",
                "service": {
                    "origin": {
                        "address": origin_address,
                        "locality": origin_locality,
                        "postal_code": origin_postal_code or None,
                        "latitude": origin_latitude,
                        "longitude": origin_longitude,
                    },
                    "destination": {
                        "address": destination_address,
                        "locality": destination_locality,
                        "postal_code": destination_postal_code or None,
                        "latitude": destination_latitude,
                        "longitude": destination_longitude,
                    },
                    "start_date": start_date,
                    "people_number": people_number,
                    "suitcases_number": suitcases_number,
                    "vehicle_size": {
                        "id": 2 if vehicle_size_id == 2 else 1,
                    },
                    "observations": observations,
                    "is_transfer": is_transfer,
                },
            }

            data = await services_client.create_taxi_service(payload)

            # 🔥 CORREGIDO: Verificar que data existe antes de acceder a sus métodos
            if data and data.get("service_created") and calls_client:
                service_id = None
                if data.get("nest_service"):
                    service_id = data.get("nest_service").get("id")
                elif data.get("result"):
                    service_id = data.get("result").get("id")
                
                if service_id:
                    await calls_client.mark_service_created(service_id)
                    logger.info(f"✅ Servicio {service_id} marcado en llamada {calls_client.current_call_sid}")

            await params.result_callback({
                "success": True,
                "service_created": True,
                "result": data,
                "message": "¡Reserva confirmada! Tu taxi está solicitado.",
            })

        except Exception as e:
            logger.error(f"❌ Error en create_taxi_service: {e}")
            await params.result_callback({
                "success": False,
                "service_created": False,
                "error": str(e),
                "message": "Tuve un problema creando la reserva. Por favor, intenta de nuevo.",
            })

    llm.register_function("check_user_status", check_user_status)
    llm.register_function("register_user", register_user)
    llm.register_function("resolve_address", resolve_address)
    llm.register_function("create_taxi_service", create_taxi_service)

    logger.info("✅ Registered tools for web bot")

    check_user_schema = FunctionSchema(
        name="check_user_status",
        description=(
            "Verifica si un usuario existe usando su número de teléfono. "
            "Debes llamarla justo después de que el cliente te dé su número."
        ),
        properties={
            "phone": {
                "type": "string",
                "description": "Número de teléfono del cliente",
            }
        },
        required=["phone"],
    )

    register_user_schema = FunctionSchema(
        name="register_user",
        description=(
            "Registra un usuario nuevo usando su número de teléfono y nombre completo. "
            "Solo debes llamarla después de que el cliente haya dicho su nombre."
        ),
        properties={
            "phone": {
                "type": "string",
                "description": "Número de teléfono del cliente",
            },
            "name": {
                "type": "string",
                "description": "Nombre completo del cliente",
            },
        },
        required=["phone", "name"],
    )

    resolve_address_schema = FunctionSchema(
        name="resolve_address",
        description=(
            "Resuelve una dirección en texto libre dentro de España. "
            "Debes usarla SIEMPRE que el cliente mencione una dirección de recogida o destino."
        ),
        properties={
            "address_text": {
                "type": "string",
                "description": "Dirección en texto libre del cliente",
            }
        },
        required=["address_text"],
    )

    create_taxi_service_schema = FunctionSchema(
        name="create_taxi_service",
        description=(
            "Crea un servicio de taxi cuando ya tienes recogida y destino validados, "
            "además de la fecha y hora del servicio."
        ),
        properties={
            "nest_client_id": {
                "type": "integer",
                "description": "ID del cliente en Nest",
            },
            "origin_address": {"type": "string", "description": "Dirección de recogida"},
            "origin_locality": {"type": "string", "description": "Localidad de recogida"},
            "origin_latitude": {"type": "number", "description": "Latitud de recogida"},
            "origin_longitude": {"type": "number", "description": "Longitud de recogida"},
            "destination_address": {"type": "string", "description": "Dirección de destino"},
            "destination_locality": {"type": "string", "description": "Localidad de destino"},
            "destination_latitude": {"type": "number", "description": "Latitud de destino"},
            "destination_longitude": {"type": "number", "description": "Longitud de destino"},
            "start_date": {
                "type": "string",
                "description": "Fecha y hora en formato Madrid, ej: 2026-03-09 20:30:00",
            },
            "people_number": {
                "type": "integer",
                "description": "Número de personas",
                "default": 1,
            },
            "suitcases_number": {
                "type": "integer",
                "description": "Número de maletas",
                "default": 0,
            },
            "vehicle_size_id": {
                "type": "integer",
                "description": "1 para normal, 2 para grande",
                "default": 1,
            },
            "origin_postal_code": {
                "type": "string",
                "description": "Código postal de recogida",
                "default": "",
            },
            "destination_postal_code": {
                "type": "string",
                "description": "Código postal de destino",
                "default": "",
            },
            "observations": {
                "type": "string",
                "description": "Observaciones",
                "default": "",
            },
            "is_transfer": {
                "type": "boolean",
                "description": "Es transfer",
                "default": False,
            },
        },
        required=[
            "nest_client_id",
            "origin_address",
            "origin_locality",
            "origin_latitude",
            "origin_longitude",
            "destination_address",
            "destination_locality",
            "destination_latitude",
            "destination_longitude",
            "start_date",
        ],
    )

    return ToolsSchema(
        standard_tools=[
            check_user_schema,
            register_user_schema,
            resolve_address_schema,
            create_taxi_service_schema,
        ]
    )