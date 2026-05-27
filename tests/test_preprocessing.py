from services.common.preprocessing import build_feature_frame, clean_payload


def test_clean_payload_ignores_targets_and_identifier() -> None:
    payload = {
        "CustomerID": "123",
        "Churn Value": 1,
        "Churn Score": 99,
        "Tenure Months": "12",
        "Total Charges": "150.5",
        "Contract": "Month-to-month",
    }

    cleaned = clean_payload(payload)

    assert "CustomerID" not in cleaned
    assert "Churn Value" not in cleaned
    assert "Churn Score" not in cleaned
    assert cleaned["Tenure Months"] == 12
    assert cleaned["Total Charges"] == 150.5


def test_build_feature_frame_aligns_missing_columns() -> None:
    frame = build_feature_frame(
        [{"Tenure Months": "5", "Contract": "Month-to-month"}],
        feature_columns=["Tenure Months", "Monthly Charges", "Contract"],
    )

    assert list(frame.columns) == ["Tenure Months", "Monthly Charges", "Contract"]
    assert frame.loc[0, "Tenure Months"] == 5
    assert frame.loc[0, "Contract"] == "Month-to-month"
    assert frame["Monthly Charges"].isna().iloc[0]