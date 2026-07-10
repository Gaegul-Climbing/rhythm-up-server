import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status

from app.database.dependencies import SessionDependency
from app.domains.accounts.dependencies import CurrentUserDependency
from app.domains.reservations.availability import get_availability
from app.domains.reservations.dependencies import HoldStoreDependency
from app.domains.reservations.hold_service import (
    create_hold,
    get_user_hold,
    release_user_hold,
)
from app.domains.reservations.schemas import (
    AvailabilityResponse,
    HoldCreateRequest,
    HoldResponse,
    ReservationCreateRequest,
    ReservationResponse,
)
from app.domains.reservations.service import (
    cancel_reservation,
    confirm_reservation,
    find_user_reservation,
    find_user_reservations,
)

router = APIRouter()


def hold_response(hold) -> HoldResponse:
    return HoldResponse(
        id=hold.id,
        user_id=hold.user_id,
        branch_id=hold.branch_id,
        room_id=hold.room_id,
        start_at=hold.start_at,
        end_at=hold.end_at,
        duration_hours=hold.duration_hours,
        expires_at=hold.expires_at,
    )


@router.get(
    "/branches/{branch_id}/rooms/{room_id}/availability",
    response_model=AvailabilityResponse,
)
async def read_availability(
    branch_id: UUID,
    room_id: UUID,
    date: datetime.date,
    session: SessionDependency,
    store: HoldStoreDependency,
) -> AvailabilityResponse:
    return await get_availability(
        session=session,
        store=store,
        branch_id=branch_id,
        room_id=room_id,
        target_date=date,
    )


@router.post(
    "/reservation-holds",
    response_model=HoldResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation_hold(
    request: HoldCreateRequest,
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
) -> HoldResponse:
    hold = await create_hold(
        session=session,
        store=store,
        user_id=current_user.id,
        branch_id=request.branch_id,
        room_id=request.room_id,
        start_at=request.start_at,
        duration_hours=request.duration_hours,
    )
    return hold_response(hold)


@router.get("/reservation-holds/{hold_id}", response_model=HoldResponse)
async def read_reservation_hold(
    hold_id: UUID,
    current_user: CurrentUserDependency,
    store: HoldStoreDependency,
) -> HoldResponse:
    hold = await get_user_hold(store=store, user_id=current_user.id, hold_id=hold_id)
    return hold_response(hold)


@router.delete("/reservation-holds/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation_hold(
    hold_id: UUID,
    current_user: CurrentUserDependency,
    store: HoldStoreDependency,
) -> Response:
    await release_user_hold(store=store, user_id=current_user.id, hold_id=hold_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    request: ReservationCreateRequest,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=100),
    ],
    current_user: CurrentUserDependency,
    session: SessionDependency,
    store: HoldStoreDependency,
) -> ReservationResponse:
    reservation = await confirm_reservation(
        session=session,
        store=store,
        user_id=current_user.id,
        hold_id=request.hold_id,
        idempotency_key=idempotency_key,
    )
    return ReservationResponse.model_validate(reservation)


@router.get("/reservations", response_model=list[ReservationResponse])
async def read_reservations(
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> list[ReservationResponse]:
    reservations = await find_user_reservations(session, current_user.id)
    return [ReservationResponse.model_validate(item) for item in reservations]


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
async def read_reservation(
    reservation_id: UUID,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> ReservationResponse:
    reservation = await find_user_reservation(session, current_user.id, reservation_id)
    return ReservationResponse.model_validate(reservation)


@router.delete("/reservations/{reservation_id}", response_model=ReservationResponse)
async def delete_reservation(
    reservation_id: UUID,
    current_user: CurrentUserDependency,
    session: SessionDependency,
) -> ReservationResponse:
    reservation = await cancel_reservation(
        session=session,
        user_id=current_user.id,
        reservation_id=reservation_id,
    )
    return ReservationResponse.model_validate(reservation)
