# from address_extract import address_extract, utils
from .address_extract import address_extract, utils
from fuzzywuzzy import fuzz
from itertools import permutations


class AddressComparer:
    def __init__(self):
        order = ('street', 'ward', 'district', 'province')
        self.extractor = address_extract.AddressExtractor()
        self.__group_keys = order
        self.__possibilities = tuple(permutations(order, len(order)))

    def _extract_as_four_group(self, addr: str, group_keys: tuple):
        if len(addr) > 0:
            groups = addr.split(',')
            for i in range(len(groups)):
                groups[i] = groups[i].strip()
            groups = [e for e in groups if len(e) > 0]
            # If more than 4 elements then merged all head elements into one
            if len(groups) > 4:
                boundary = len(groups) - 3
                all_head_in_one = ' '.join(groups[0:boundary])
                groups = [all_head_in_one] + groups[boundary:]
        else:
            groups = ['', '', '', '']
        # Mapping values from address groups, address groups is assumpted to be smaller than groups keys
        result = dict()
        for i in range(len(group_keys)):
            try:
                value = groups[i]
            except Exception:
                value = ''
            result[group_keys[i]] = value
        return result

    def _full_string_compare(self, addr1: str, addr2: str):
        result = {'normal_ratio': 0, 'partial_ratio': 0}
        if len(addr1) <= 0 or len(addr2) <= 0:
            return result
        result['normal_ratio'] = fuzz.token_sort_ratio(addr1, addr2)
        result['partial_ratio'] = fuzz.token_set_ratio(addr1, addr2)
        return result

    def _group_compare(self, addr1, addr2, pos_addr1=None, pos_addr2=None):
        result = dict()
        if type(addr1) is str and type(addr2) is str:
            if None in (pos_addr1, pos_addr2):
                addr1_as_groups = self._extract_as_four_group(addr1, self.__group_keys)
                addr2_as_groups = self._extract_as_four_group(addr2, self.__group_keys)
            else:
                addr1_as_groups = self._extract_as_four_group(addr1, pos_addr1)
                addr2_as_groups = self._extract_as_four_group(addr2, pos_addr2)
        elif type(addr1) is dict and type(addr2) is dict:
            addr1_as_groups = addr1
            addr2_as_groups = addr2
        else:
            for k in self.__group_keys:
                result[k] = 0
            return result
        # Do some trick to increased matching rate
        for k in self.__group_keys:
            addr1_as_groups[k] = utils.clean_and_reduce_length(addr1_as_groups[k], biased_group=k)
            addr2_as_groups[k] = utils.clean_and_reduce_length(addr2_as_groups[k], biased_group=k)

        for k in self.__group_keys:
            if len(addr1_as_groups[k]) == 0 and len(addr2_as_groups[k]) == 0:
                ratio = 0.01
            elif len(addr1_as_groups[k]) > 0 and len(addr2_as_groups[k]) > 0:
                ratio = fuzz.partial_ratio(addr1_as_groups[k], addr2_as_groups[k])
            else:
                ratio = 0
            result[k] = ratio
            # print("Ratio is {}".format(ratio))
            # print(k)
        return result

    def _long_brute_compare(self, cleaned_addr_1, cleaned_addr_2):
        brute_result = {}
        for k in self.__group_keys:
            brute_result[k] = []
        for pos in self.__possibilities:
            addr_as_dict = self._extract_as_four_group(cleaned_addr_1, group_keys=pos)
            for com in self.__possibilities:
                compare_addr_as_dict = self._extract_as_four_group(cleaned_addr_2, group_keys=com)
                result = self._group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=pos,
                                             pos_addr2=com)
                for k in self.__group_keys:
                    brute_result[k].append(result[k])
        # print("long brute compare")
        return brute_result

    def _do_compare_one_to_many_for_brute_compare(self, cleaned_addr_1, cleaned_addr_2, is_reversed=None):
        final_result = {'addr1_pos': None, 'addr2_pos': None}
        no_of_possibility = len(self.__possibilities)
        # To work with addresses which can be splited into >= 2 parts
        brute_result = None
        if is_reversed is None:
            brute_result = self._long_brute_compare(cleaned_addr_1, cleaned_addr_2)
        # is_reversed is flag to work with all-in-one address
        elif not is_reversed:
            brute_result = self._long_brute_compare(cleaned_addr_1, cleaned_addr_2)
        elif is_reversed:
            brute_result = self._long_brute_compare(cleaned_addr_2, cleaned_addr_1)
        index = self._index_best_match(brute_result, no_of_possibility, no_of_possibility)
        if brute_result is not None:
            if index >= 0:
                for k in self.__group_keys:
                    final_result[k] = brute_result[k][index]
                outter_index = index // no_of_possibility
                inner_index = index % no_of_possibility
                if is_reversed is None:
                    final_result['addr1_pos'] = self.__possibilities[outter_index]
                    final_result['addr2_pos'] = self.__possibilities[inner_index]
                elif not is_reversed:
                    final_result['addr1_pos'] = self.__possibilities[outter_index]
                    final_result['addr2_pos'] = self.__possibilities[inner_index]
                else:
                    final_result['addr2_pos'] = self.__possibilities[outter_index]
                    final_result['addr1_pos'] = self.__possibilities[inner_index]
                return final_result
        for k in self.__group_keys:
            final_result[k] = 0.1
        return final_result

    def _compare_address_one_to_many(self, addr, compare_addr, biased_order):
        brute_result = {}
        for k in self.__group_keys:
            brute_result[k] = []
        addr_as_dict = self._extract_as_four_group(addr, group_keys=biased_order)
        for com in self.__possibilities:
            compare_addr_as_dict = self._extract_as_four_group(compare_addr, group_keys=com)
            result = self._group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=biased_order,
                                         pos_addr2=com)
            for k in self.__group_keys:
                brute_result[k].append(result[k])
        return brute_result

    def _index_best_match(self, brute_result: dict, no_of_possibility_outer: int, no_of_possibility_inner: int):
        max_value = 0
        index = -1
        key_biases = {'province': 0.4, 'district': 0.3, 'ward': 0.2, 'street': 0.1}

        for i in range(no_of_possibility_outer * no_of_possibility_inner):
            average = 0
            province_ratio = brute_result['province'][i]
            if province_ratio <= 13:
                continue
            else:
                for o in self.__group_keys:
                    average += brute_result[o][i] * key_biases[o]
            if average > max_value:
                max_value = average
                index = i
        return index

    def _index_best_match_no_biased(self, brute_result: dict, no_of_possibility_outer: int,
                                    no_of_possibility_inner: int):
        max_value = 0
        index = -1
        for i in range(no_of_possibility_outer * no_of_possibility_inner):
            average = 0
            for o in self.__group_keys:
                average += brute_result[o][i]
            if average >= max_value:
                max_value = average
                index = i
        return index

    def _inject_all_into_groups(self, addr):
        new_addr_group = []
        for _ in range(len(self.__group_keys)):
            new_addr_group.append(addr)
        new_addr = ','.join(new_addr_group)
        return new_addr

    def brute_compare(self, addr: str, compare_addr: str, is_cleaned=False, no_part_of_addr=4,
                      no_part_of_compare_addr=4):
        final_result = {'addr1_pos': None, 'addr2_pos': None}
        # brute_result = {}
        for k in self.__group_keys:
            # brute_result[k] = []
            final_result[k] = 0

        if not is_cleaned:
            cleaned_addr = utils.clean_alphanumeric_delimeter_upper(addr)
            cleaned_compare_addr = utils.clean_alphanumeric_delimeter_upper(compare_addr)
        else:
            cleaned_addr, cleaned_compare_addr = addr, compare_addr
        final_result['cleaned_addr1'] = cleaned_addr
        final_result['cleaned_addr2'] = cleaned_compare_addr

        if no_part_of_addr == 1 and no_part_of_compare_addr == 1:
            # Should add handling for too-short string
            # if len(cleaned_addr) > 3 and len(cleaned_compare_addr) > 3:
            #     biased_order = ('street', 'ward', 'district', 'province')
            #     new_addr_1 = self._inject_all_into_groups(cleaned_addr)
            #     new_addr_2 = self._inject_all_into_groups(cleaned_compare_addr)
            #     addr_as_dict = self._extract_as_four_group(new_addr_1, group_keys=biased_order)
            #     compare_addr_as_dict = self._extract_as_four_group(new_addr_2, group_keys=biased_order)
            #     result = self._group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=biased_order,
            #                                  pos_addr2=biased_order)
            #     final_result.update(result)
            #     final_result['addr1_pos'] = biased_order
            #     final_result['addr2_pos'] = biased_order
            if len(cleaned_addr) > 3 and len(cleaned_compare_addr) > 3:
                biased_order = ('province', 'street', 'ward', 'district')
                addr_as_dict = self._extract_as_four_group(cleaned_addr, group_keys=biased_order)
                compare_addr_as_dict = self._extract_as_four_group(cleaned_compare_addr, group_keys=biased_order)
                result = self._group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=biased_order,
                                             pos_addr2=biased_order)
                final_result.update(result)
                final_result['addr1_pos'] = biased_order
                final_result['addr2_pos'] = biased_order

        elif no_part_of_addr == 1 or no_part_of_compare_addr == 1:
            compare_result = None
            # Do clean, reduce and inject all-in-one string into each group of the address
            if no_part_of_addr == 1:
                # Should add handling for too-short string
                if len(cleaned_addr) > 3:
                    new_addr = self._inject_all_into_groups(cleaned_addr)
                    compare_result = self._do_compare_one_to_many_for_brute_compare(cleaned_addr_1=new_addr,
                                                                                    cleaned_addr_2=cleaned_compare_addr,
                                                                                    is_reversed=False)
            else:
                # Should add handling for too-short string
                if len(cleaned_compare_addr) > 3:
                    new_addr = self._inject_all_into_groups(cleaned_compare_addr)
                    compare_result = self._do_compare_one_to_many_for_brute_compare(cleaned_addr_1=cleaned_addr,
                                                                                    cleaned_addr_2=new_addr,
                                                                                    is_reversed=True)
            if compare_result is not None:
                final_result.update(compare_result)
        else:
            compare_result = self._do_compare_one_to_many_for_brute_compare(cleaned_addr_1=cleaned_addr,
                                                                            cleaned_addr_2=cleaned_compare_addr)
            final_result.update(compare_result)
        return final_result

    def _write_compare_result(self, search_type: str, mapped_addr: dict, mapped_compare: dict, full_string_result: dict,
                              group_result: dict):
        mapped_addr1_result, mapped_addr2_result = {}, {}
        mapped_addr1, mapped_addr2 = {}, {}

        group_result['addr1_pos'] = str(group_result.get('addr1_pos', ''))
        group_result['addr2_pos'] = str(group_result.get('addr2_pos', ''))

        final_result = dict(full_string_result)
        final_result.update(group_result)

        # Write mapped values
        for k in self.__group_keys:
            k1 = k + '_1'
            k2 = k + '_2'
            if mapped_addr is None:
                mapped_addr1_result[k1] = 'error'
            else:
                mapped_addr1_result[k1] = mapped_addr[k].upper()
                mapped_addr1[k] = mapped_addr[k].upper()

            if mapped_compare is None:
                mapped_addr2_result[k2] = 'error'
            else:
                mapped_addr2_result[k2] = mapped_compare[k].upper()
                mapped_addr2[k] = mapped_compare[k].upper()

        # For evaluation
        mapped_addr1_result['count'] = mapped_addr.get('count', 0)
        mapped_addr2_result['count'] = mapped_compare.get('count', 0)

        final_result.update(mapped_addr1_result)
        final_result.update(mapped_addr2_result)

        # Evaluate matching ratio after mapping
        mapped_group_result = self._group_compare(mapped_addr1, mapped_addr2)

        # Use space as delimeter to work with fuzz's comparing functions
        mapped_addr_as_string = ' '.join(mapped_addr1.values())
        mapped_compare_as_string = ' '.join(mapped_addr2.values())
        mapped_full_string_result = self._full_string_compare(mapped_addr_as_string, mapped_compare_as_string)

        final_result['mapped_normal_ratio'] = mapped_full_string_result.get('normal_ratio', 0.01)
        final_result['mapped_partial_ratio'] = mapped_full_string_result.get('partial_ratio', 0.01)

        for k in self.__group_keys:
            key = k + '_mapped_ratio'
            if mapped_group_result is not None:
                final_result[key] = mapped_group_result[k]
            else:
                final_result[key] = 0
        final_result['type'] = search_type
        return final_result

    def _rebuild_addresses(self, addr_pos: tuple, cleaned_addr: str):
        rebuilt_addr = []
        # Extract with a preferred order
        key_value_pairs = utils.extract_group(cleaned_addr, addr_pos)
        # Build with a fixed order
        for o in self.__group_keys:
            rebuilt_addr.append(key_value_pairs.get(o, ''))
        # AddressExtractor expect to work with ',' as the delimeter among groups
        return ','.join(rebuilt_addr)

    def _compare_with_assumption_brute_force_search(self, cleaned_addr1, cleaned_addr2, key_value_pairs1,
                                                    key_value_pairs2):
        no_of_groups_addr1 = len(key_value_pairs1.keys())
        no_of_groups_addr2 = len(key_value_pairs2.keys())

        # Try to find the best matching possibilities for address 1 and 2
        brute_result = self.brute_compare(cleaned_addr1, cleaned_addr2, is_cleaned=True,
                                          no_part_of_addr=no_of_groups_addr1,
                                          no_part_of_compare_addr=no_of_groups_addr2
                                          )
        addr1_pos = brute_result.get('addr1_pos')
        addr2_pos = brute_result.get('addr2_pos')

        if no_of_groups_addr1 == 0 or no_of_groups_addr2 == 0:
            return None
        elif no_of_groups_addr1 == 1 and no_of_groups_addr2 == 1:
            cleaned_addr1 = self._inject_all_into_groups(cleaned_addr1)
            cleaned_addr2 = self._inject_all_into_groups(cleaned_addr2)
        # If found, use that info to create an preferred order
        else:
            if addr1_pos is not None and addr2_pos is not None:
                # Extract with addr1_pos/addr2_pos and rebuild with standard order street,ward,district,province
                cleaned_addr1 = self._rebuild_addresses(addr1_pos, cleaned_addr1)
                cleaned_addr2 = self._rebuild_addresses(addr2_pos, cleaned_addr2)

        # Try to find standardized province, district and ward
        # assumption_brute_force_search() expect an address as: street, ward, district, province
        fall_back_result = dict()
        for k in self.__group_keys:
            fall_back_result[k] = ""
        fall_back_result['city_rate'] = 0
        fall_back_result['all_rate'] = 0
        fall_back_result['type'] = "short_address"
        fall_back_result['count'] = 0
        # Every group should > 3 characters and + 3 delimeters
        # print(cleaned_addr1)
        mapped_addr, mapped_compare = None, None
        if len(cleaned_addr1) > 15:
            # mapped_addr = self.extractor.assumption_brute_force_search_word_bag(cleaned_addr1, extra_rate=60)
            mapped_addr = self.extractor.assumption_brute_force_search(cleaned_addr1, extra_rate=60)
            # mapped_addr = self.extractor.assumption_brute_force_search(cleaned_addr1)
        # the above block can also return None
        if mapped_addr is None:
            mapped_addr = fall_back_result
        # print(cleaned_addr2)
        if len(cleaned_addr2) > 15:
            # mapped_compare = self.extractor.assumption_brute_force_search_word_bag(cleaned_addr2, extra_rate=60)
            mapped_compare = self.extractor.assumption_brute_force_search(cleaned_addr2, extra_rate=60)
            # mapped_compare = self.extractor.assumption_brute_force_search(cleaned_addr2)
        if mapped_compare is None:
            mapped_compare = fall_back_result

        full_string_result = self._full_string_compare(cleaned_addr1, cleaned_addr2)
        search_type = mapped_addr.get('type', '') + '_' + mapped_compare.get('type', '')

        # Evaluate and return both results of before and after mapping
        final_result = self._write_compare_result(search_type=search_type, mapped_addr=mapped_addr,
                                                  mapped_compare=mapped_compare,
                                                  full_string_result=full_string_result, group_result=brute_result
                                                  )
        return final_result

    def fuzzy_compare(self, addr: str, compare_addr: str):

        # Decide how many part/group of the address: expected a dict with 0->4 groups
        key_value_pairs1 = utils.extract_group(addr, self.__group_keys)
        key_value_pairs2 = utils.extract_group(compare_addr, self.__group_keys)

        # Do simple cleaning
        cleaned_addr1 = utils.clean_alphanumeric_delimeter_upper(addr)
        cleaned_addr2 = utils.clean_alphanumeric_delimeter_upper(compare_addr)
        return self._compare_with_assumption_brute_force_search(cleaned_addr1, cleaned_addr2,
                                                                key_value_pairs1=key_value_pairs1,
                                                                key_value_pairs2=key_value_pairs2
                                                                )
