"""Gematria utility classes."""

HEBREW_NUMBERS_AVAILABLE = True


class Gematria:
    """Helper methods for working with Hebrew gematria numbers."""

    _hebrew_letters_map = {
        1: "א",
        2: "ב",
        3: "ג",
        4: "ד",
        5: "ה",
        6: "ו",
        7: "ז",
        8: "ח",
        9: "ט",
        10: "י",
        20: "כ",
        30: "ל",
        40: "מ",
        50: "נ",
        60: "ס",
        70: "ע",
        80: "פ",
        90: "צ",
        100: "ק",
        200: "ר",
        300: "ש",
        400: "ת",
        500: "תק",
        600: "תר",
        700: "תש",
        800: "תת",
        900: "תתק",
    }

    _hebrew_letter_values = {
        "א": 1,
        "ב": 2,
        "ג": 3,
        "ד": 4,
        "ה": 5,
        "ו": 6,
        "ז": 7,
        "ח": 8,
        "ט": 9,
        "י": 10,
        "כ": 20,
        "ך": 20,
        "ל": 30,
        "מ": 40,
        "ם": 40,
        "נ": 50,
        "ן": 50,
        "ס": 60,
        "ע": 70,
        "פ": 80,
        "ף": 80,
        "צ": 90,
        "ץ": 90,
        "ק": 100,
        "ר": 200,
        "ש": 300,
        "ת": 400,
    }

    @classmethod
    def format_hebrew_number(cls, num: int, punctuation: bool = True) -> str:
        """Return the Hebrew gematria representation of ``num``."""
        if not isinstance(num, int) or not (1 <= num <= 9999):
            return str(num)

        result: list[str] = []
        thousands = num // 1000
        if thousands > 0 and thousands in cls._hebrew_letters_map:
            result.append(cls._hebrew_letters_map[thousands] + "׳")

        remainder = num % 1000
        if remainder == 0 and thousands > 0:
            pass
        elif remainder == 15:
            result.append("טו")
        elif remainder == 16:
            result.append("טז")
        else:
            hundreds = (remainder // 100) * 100
            tens_units = remainder % 100

            if hundreds > 0:
                result.append(cls._hebrew_letters_map.get(hundreds, ""))

            if tens_units > 0 and tens_units not in {15, 16}:
                tens = (tens_units // 10) * 10
                units = tens_units % 10
                if tens > 0:
                    result.append(cls._hebrew_letters_map.get(tens, ""))
                if units > 0:
                    result.append(cls._hebrew_letters_map.get(units, ""))

        final_string = "".join(result)

        if punctuation and len(final_string) > 1:
            if final_string[-1] == "׳":
                pass
            elif "׳" in final_string:
                parts = final_string.split("׳")
                if len(parts[1]) > 0:
                    final_string = parts[0] + "׳" + parts[1][:-1] + "״" + parts[1][-1]
            elif final_string and final_string[-1] != "׳":
                final_string = final_string[:-1] + "״" + final_string[-1]

        return final_string

    @classmethod
    def gematria_to_int(cls, hebrew: str) -> int:
        """Convert a Hebrew gematria string into an integer."""
        total = 0
        cleaned_hebrew = hebrew.replace("׳", "").replace("״", "")
        for ch in cleaned_hebrew:
            total += cls._hebrew_letter_values.get(ch, 0)
        return total
