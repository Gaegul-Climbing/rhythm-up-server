# 예약 취소와 환불 정책

리듬업 연습실의 유료 예약은 결제 승인 후에만 확정됩니다. 따라서 예약 취소는 객실 슬롯을 다시 여는 작업과 결제 취소를 함께 처리해야 합니다.

## 현재 정책

- 이용 시작 시각 **24시간 전까지** 고객이 예약을 취소할 수 있습니다.
- 기한 안에 취소하면 승인된 결제를 **전액 환불**합니다.
- 결제 provider의 취소가 성공한 경우에만 예약 상태를 `cancelled`로 바꾸고 예약 슬롯을 삭제합니다.
- 결제 취소가 실패하거나 부분 취소 상태라면 예약은 `confirmed` 상태로 유지합니다.
- 기존 학습 데이터처럼 결제 주문이 연결되지 않은 예약은 결제 취소 없이 예약만 취소할 수 있습니다.

## 상태 전이

```text
approved payment + confirmed reservation
→ provider cancel/refund succeeds
→ payment: refunded
→ payment order: cancelled
→ reservation: cancelled
→ reservation slots deleted
```

외부 결제 취소는 데이터베이스 트랜잭션과 하나의 원자적 작업으로 묶을 수 없습니다. provider 취소 후 DB 상태 저장에 실패하면 API는 `reservation_cancellation_reconciliation_required` 오류를 반환합니다. 이 경우 외부 결제와 내부 상태를 확인하는 reconciliation 절차가 필요합니다.

부분 환불, 수수료 공제, 관리자 취소, 취소 기한의 지점별 차등 정책은 이후 운영 정책이 확정될 때 별도 상태와 금액 필드로 확장합니다.
