import json
import re
from typing import List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import get_settings, get_logger
from src.core.models import ProcessingResult
from src.interfaces import IExportProvider
from .base import BaseExportProvider


logger = get_logger(__name__)


class GoogleSheetsProvider(BaseExportProvider, IExportProvider):
    """Export to Google Sheets"""
    
    # Standard column order for the Excel output
    COLUMNS = [
        "date", "vehicle_number", "driver_name", "party_name",
        "item_name", "gross_weight", "tare_weight", "net_weight",
        "quantity", "amount", "tax_amount", "total_amount",
        "transit_pass_number", "origin", "destination", "distance",
        "receipt_type", "confidence", "status"
    ]
    
    def __init__(self):
        settings = get_settings()
        self.sheet_id = self._extract_sheet_id(settings.GOOGLE_SHEET_ID)
        self.creds_file = settings.GOOGLE_SHEETS_CREDENTIALS
        self.service = None
        self._init_service()
    
    def _init_service(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.creds_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=credentials)
    
    async def export(self, results: List[ProcessingResult]) -> str:
        """Batch export to new sheet or tab"""
        self._ensure_header_row()
        rows = [self.COLUMNS]  # Header
        
        for result in results:
            rows.append(self._result_to_row(result))
        
        # Append to sheet
        body = {'values': rows}
        result = self.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
        
        logger.info(f"Exported {len(results)} records to sheets")
        return result.get('updates', {}).get('spreadsheetId', '')
    
    async def append_single(self, result: ProcessingResult) -> bool:
        """Append single result"""
        try:
            self._ensure_header_row()
            row = self._result_to_row(result)
            body = {'values': [row]}
            
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A1',
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"Failed to append to sheets: {e}")
            return False
    
    def _result_to_row(self, result: ProcessingResult) -> List[str]:
        """Convert ProcessingResult to row values"""
        if not result.extracted_receipt:
            return [""] * len(self.COLUMNS)
        
        fields = result.extracted_receipt.fields
        get_val = lambda k: self._normalize_for_sheets(
            fields.get(k, type('obj', (object,), {'value': ''})()).value
        )
        
        return [
            get_val("date"),
            get_val("vehicle_number"),
            get_val("driver_name"),
            get_val("party_name"),
            get_val("item_name"),
            get_val("gross_weight"),
            get_val("tare_weight"),
            get_val("net_weight"),
            get_val("quantity"),
            get_val("amount"),
            get_val("tax_amount"),
            get_val("total_amount"),
            get_val("transit_pass_number"),
            get_val("origin"),
            get_val("destination"),
            get_val("distance"),
            result.extracted_receipt.receipt_type.name,
            str(result.extracted_receipt.get_overall_confidence()),
            result.status.name
        ]

    def _extract_sheet_id(self, sheet_id_or_url: str) -> str:
        """Accept either raw spreadsheet ID or full Google Sheets URL."""
        value = (sheet_id_or_url or "").strip()
        if not value:
            return value

        # URL format: https://docs.google.com/spreadsheets/d/<ID>/edit...
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", value)
        if match:
            return match.group(1)

        return value

    def _ensure_header_row(self) -> None:
        """
        Ensure first row contains the configured headers.
        If sheet already has data without headers, insert a new top row and write headers.
        """
        header_range = f"Sheet1!A1:{self._column_letter(len(self.COLUMNS))}1"
        response = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=header_range
        ).execute()

        existing = response.get("values", [])
        if not existing:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": [self.COLUMNS]}
            ).execute()
            return

        first_row = existing[0]
        if first_row == self.COLUMNS:
            return

        # Existing data is present but headers are missing/mismatched: prepend header row.
        sheet_id = self._get_sheet_id("Sheet1")
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={
                "requests": [
                    {
                        "insertDimension": {
                            "range": {
                                "sheetId": sheet_id,
                                "dimension": "ROWS",
                                "startIndex": 0,
                                "endIndex": 1
                            },
                            "inheritFromBefore": False
                        }
                    }
                ]
            }
        ).execute()

        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [self.COLUMNS]}
        ).execute()

    def _column_letter(self, index: int) -> str:
        """1-based index -> Excel column letters (e.g. 1=A, 27=AA)."""
        result = ""
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def _get_sheet_id(self, title: str) -> int:
        """Resolve sheet numeric ID by title, fallback to first sheet."""
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.sheet_id
        ).execute()
        sheets = spreadsheet.get("sheets", [])
        for sheet in sheets:
            props = sheet.get("properties", {})
            if props.get("title") == title:
                return props.get("sheetId")
        if not sheets:
            raise ValueError("Spreadsheet has no sheets")
        return sheets[0].get("properties", {}).get("sheetId")
