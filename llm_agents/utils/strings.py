from fuzzywuzzy import fuzz


class StringOps:

    @classmethod
    def compare_strings(cls, str1: str, str2: str, method: str = "ratio"):

        str1 = str1.upper()
        str2 = str2.upper()

        if method == "ratio":
            return fuzz.ratio(str1, str2)
        elif method == "partial_ratio":
            return fuzz.partial_ratio(str1, str2)
        elif method == "token_sort_ratio":
            return fuzz.token_sort_ratio(str1, str2)
        elif method == "token_set_ratio":
            return fuzz.token_set_ratio(str1, str2)
        else:
            raise ValueError(
                "Invalid method. Choose from 'ratio', 'partial_ratio', 'token_sort_ratio', or 'token_set_ratio'."
            )

    @classmethod
    def find_most_similar(cls, input_value: str, list_values: list[str]):
        similarities: list[tuple[str, str, int]] = [
            (input_value, value, cls.compare_strings(value, input_value))
            for value in list_values
        ]
        similarities = sorted(similarities, key=lambda x: x[2], reverse=True)
        return similarities
