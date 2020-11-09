from address_extract import address_extract
from address_extract import utils

from fuzzywuzzy import fuzz


def extract_as_four_group(addr: str, group_keys: tuple):
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
        except:
            value = ''
        result[group_keys[i]] = value
    return result


def group_compare(addr1, addr2, pos_addr1=None, pos_addr2=None):
    group_keys = ('street', 'ward', 'district', 'province')
    result = dict()
    if type(addr1) is str and type(addr2) is str:
        if None in (pos_addr1, pos_addr2):
            addr1_as_groups = extract_as_four_group(addr1, group_keys)
            addr2_as_groups = extract_as_four_group(addr2, group_keys)
        else:
            addr1_as_groups = extract_as_four_group(addr1, pos_addr1)
            addr2_as_groups = extract_as_four_group(addr2, pos_addr2)
    elif type(addr1) is dict and type(addr2) is dict:
        addr1_as_groups = addr1
        addr2_as_groups = addr2
        if None in (addr1_as_groups, addr2_as_groups):
            for k in group_keys:
                result[k] = 0
            return result
    else:
        for k in group_keys:
            result[k] = 0
        return result

    for k in group_keys:
        if len(addr1_as_groups[k]) == 0 and len(addr2_as_groups[k]) == 0:
            ratio = 0.01
        elif len(addr1_as_groups[k]) > 0 and len(addr2_as_groups[k]) > 0:
            ratio = fuzz.ratio(addr1_as_groups[k], addr2_as_groups[k])
        else:
            ratio = 0
        result[k] = ratio
        # print("Ratio is {}".format(ratio))
        # print(k)
    return result


def full_string_compare(addr1: str, addr2: str):
    result = {'normal_ratio': 0, 'partial_ratio': 0}
    if len(addr1) <= 0 or len(addr2) <= 0:
        return result
    result['normal_ratio'] = fuzz.ratio(addr1, addr2)
    result['partial_ratio'] = fuzz.partial_ratio(addr1, addr2)
    return result


from itertools import permutations


class AddressComparer():
    def __init__(self):
        order = ('street', 'ward', 'district', 'province')
        self.extractor = address_extract.AddressExtractor()
        self.group_keys = order
        self.possibilities = list(permutations(order, len(order)))

    def _compare_address_one_to_many(self, cleaned_addr, cleaned_compare_addr, biased_order):
        brute_result = {}
        for k in self.group_keys:
            brute_result[k] = []
        addr_as_dict = extract_as_four_group(cleaned_addr, group_keys=biased_order)
        for com in self.possibilities:
            compare_addr_as_dict = extract_as_four_group(cleaned_compare_addr, group_keys=com)
            result = group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=biased_order,
                                   pos_addr2=com)
            for k in self.group_keys:
                brute_result[k].append(result[k])
        return brute_result

    def _index_best_match(self, brute_result: dict, no_of_possibility_outer: int, no_of_possibility_inner: int):
        max = 0
        index = -1
        key_biases = {'province': 0.4, 'district': 0.3, 'ward': 0.2, 'street': 0.1}

        for i in range(no_of_possibility_outer * no_of_possibility_inner):
            average = 0
            province_ratio = brute_result['province'][i]
            district_ratio = brute_result['district'][i]
            ward_ratio = brute_result['ward'][i]
            if province_ratio <= 10:
                continue
            elif province_ratio <= 10 and district_ratio <= 10:
                continue
            elif province_ratio <= 10 and district_ratio <= 10 and ward_ratio <= 10:
                continue
            else:
                for o in self.group_keys:
                    average += brute_result[o][i] * key_biases[o]
            if average > max:
                max = average
                index = i
        return index

    def brute_compare(self, addr: str, compare_addr: str, is_cleaned=False, no_part_of_addr=4,
                      no_part_of_compare_addr=4):
        brute_result = {}
        no_of_possibility = len(self.possibilities)
        for k in self.group_keys:
            brute_result[k] = []
        final_result = {'addr1_pos': None, 'addr2_pos': None}
        if not is_cleaned:
            cleaned_addr = utils.clean_alphanumeric_delimeter_upper(addr)
            cleaned_compare_addr = utils.clean_alphanumeric_delimeter_upper(compare_addr)
        else:
            cleaned_addr, cleaned_compare_addr = addr, compare_addr
        final_result['cleaned_addr1'] = cleaned_addr
        final_result['cleaned_addr2'] = cleaned_compare_addr

        biased_order = ('province', 'district', 'ward', 'street')
        if no_part_of_addr == 1 and no_part_of_compare_addr == 1:
            addr_as_dict = extract_as_four_group(cleaned_addr, group_keys=biased_order)
            compare_addr_as_dict = extract_as_four_group(cleaned_compare_addr, group_keys=biased_order)
            result = group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=biased_order,
                                   pos_addr2=biased_order)
            final_result.update(result)
            final_result['addr1_pos'] = biased_order
            final_result['addr2_pos'] = biased_order
            return final_result
        elif no_part_of_addr == 1 and no_part_of_compare_addr > 1:
            compare_result = self._compare_address_one_to_many(cleaned_addr=cleaned_addr,
                                                               cleaned_compare_addr=cleaned_compare_addr,
                                                               biased_order=biased_order
                                                               )
            brute_result.update(compare_result)
            # Do a look up to find the best match
            index = self._index_best_match(brute_result, 1, no_of_possibility);
            if index >= 0:
                for k in self.group_keys:
                    final_result[k] = brute_result[k][index]
                final_result['addr1_pos'] = biased_order
                final_result['addr2_pos'] = self.possibilities[index]
                return final_result
            else:
                for k in self.group_keys:
                    final_result[k] = 0.1
                return final_result
        elif no_part_of_compare_addr == 1 and no_part_of_addr > 1:
            compare_result = self._compare_address_one_to_many(cleaned_addr=cleaned_compare_addr,
                                                               cleaned_compare_addr=cleaned_addr,
                                                               biased_order=biased_order
                                                               )
            brute_result.update(compare_result)
            # Do a look up to find the best match
            index = self._index_best_match(brute_result, 1, no_of_possibility);
            if index >= 0:
                for k in self.group_keys:
                    final_result[k] = brute_result[k][index]
                final_result['addr1_pos'] = self.possibilities[index]
                final_result['addr2_pos'] = biased_order
                return final_result
            else:
                for k in self.group_keys:
                    final_result[k] = 0.1
                return final_result
        else:
            for pos in self.possibilities:
                addr_as_dict = extract_as_four_group(cleaned_addr, group_keys=pos)
                for com in self.possibilities:
                    compare_addr_as_dict = extract_as_four_group(cleaned_compare_addr, group_keys=com)
                    result = group_compare(addr1=addr_as_dict, addr2=compare_addr_as_dict, pos_addr1=pos, pos_addr2=com)
                    for k in self.group_keys:
                        brute_result[k].append(result[k])
            print("long brute compare")
            index = self._index_best_match(brute_result, no_of_possibility, no_of_possibility)

            if index >= 0:
                for k in self.group_keys:
                    final_result[k] = brute_result[k][index]
                outter_index = index // no_of_possibility
                inner_index = index % no_of_possibility
                final_result['addr1_pos'] = self.possibilities[outter_index]
                final_result['addr2_pos'] = self.possibilities[inner_index]
                # print(index)
                # print(outter_index)
                # print(inner_index)
                # print(max)
                return final_result
            else:
                for k in self.group_keys:
                    final_result[k] = 0.1
                return final_result

    def process_compare(self, addr: str, compare_addr: str):
        # if len(addr) <= 0 or len(compare_addr) <=0:
        #     return None
        cleaned_addr = utils.clean_alphanumeric_delimeter_upper(addr)
        cleaned_compare_addr = utils.clean_alphanumeric_delimeter_upper(compare_addr)

        full_string_result = full_string_compare(cleaned_addr, cleaned_compare_addr)
        group_result = group_compare(cleaned_addr, cleaned_compare_addr)

        final_result = dict(full_string_result)
        final_result.update(group_result)

        final_result['cleaned_addr1'] = cleaned_addr
        final_result['cleaned_addr2'] = cleaned_compare_addr

        mapped_addr = self.extractor.assumption_brute_force_search(cleaned_addr)
        mapped_compare = self.extractor.assumption_brute_force_search(cleaned_compare_addr)

        mapped_addr1_result, mapped_addr2_result = {}, {}
        mapped_addr1, mapped_addr2 = {}, {}

        for k in self.group_keys:
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

        final_result.update(mapped_addr1_result)
        final_result.update(mapped_addr2_result)

        mapped_group_result = None
        mapped_full_string_result = None
        if None not in (mapped_addr, mapped_compare):
            mapped_group_result = group_compare(mapped_addr1, mapped_addr2)
            mapped_addr_as_string = ''.join(mapped_addr1.values())
            mapped_compare_as_string = ''.join(mapped_addr2.values())
            mapped_full_string_result = full_string_compare(mapped_addr_as_string, mapped_compare_as_string)

        if mapped_full_string_result is not None:
            final_result['mapped_normal_ratio'] = mapped_full_string_result.get('normal_ratio', 0.01)
            final_result['mapped_partial_ratio'] = mapped_full_string_result.get('partial_ratio', 0.01)
        else:
            final_result['mapped_normal_ratio'] = 0.01
            final_result['mapped_partial_ratio'] = 0.01

        for k in self.group_keys:
            key = k + '_mapped_ratio'
            if mapped_group_result is not None:
                final_result[key] = mapped_group_result[k]
            else:
                final_result[key] = 0
        return final_result

    def _write_compare_result(self, type: str, mapped_addr: dict, mapped_compare: dict, full_string_result: dict,
                              group_result: dict):
        mapped_addr1_result, mapped_addr2_result = {}, {}
        mapped_addr1, mapped_addr2 = {}, {}

        group_result['addr1_pos'] = str(group_result.get('addr1_pos'))
        group_result['addr2_pos'] = str(group_result.get('addr2_pos'))

        final_result = dict(full_string_result)
        final_result.update(group_result)

        for k in self.group_keys:
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

        final_result.update(mapped_addr1_result)
        final_result.update(mapped_addr2_result)

        mapped_group_result = None
        mapped_full_string_result = None
        if None not in (mapped_addr, mapped_compare):
            mapped_group_result = group_compare(mapped_addr1, mapped_addr2)
            mapped_addr_as_string = ''.join(mapped_addr1.values())
            mapped_compare_as_string = ''.join(mapped_addr2.values())
            mapped_full_string_result = full_string_compare(mapped_addr_as_string, mapped_compare_as_string)

        if mapped_full_string_result is not None:
            final_result['mapped_normal_ratio'] = mapped_full_string_result.get('normal_ratio', 0.01)
            final_result['mapped_partial_ratio'] = mapped_full_string_result.get('partial_ratio', 0.01)
        else:
            final_result['mapped_normal_ratio'] = 0.01
            final_result['mapped_partial_ratio'] = 0.01

        for k in self.group_keys:
            key = k + '_mapped_ratio'
            if mapped_group_result is not None:
                final_result[key] = mapped_group_result[k]
            else:
                final_result[key] = 0
        final_result['type'] = type
        return final_result

    def _rebuild_addresses(self, addr_pos: tuple, cleaned_addr: str):
        rebuilt_addr = []
        key_value_pairs = utils.extract_group(cleaned_addr, addr_pos)
        for o in self.group_keys:
            rebuilt_addr.append(key_value_pairs.get(o, ''))
        # AddressExtractor expect to work with ',' as the delimeter among groups
        return ','.join(rebuilt_addr)

    def _compare_with_assumption_search_sorted(self, cleaned_addr1, cleaned_addr2, key_value_pairs1, key_value_pairs2):
        no_of_groups_addr1 = len(key_value_pairs1.keys())
        no_of_groups_addr2 = len(key_value_pairs2.keys())

        brute_compare = self.brute_compare(cleaned_addr1, cleaned_addr2, is_cleaned=True,
                                           no_part_of_addr=no_of_groups_addr1,
                                           no_part_of_compare_addr=no_of_groups_addr2
                                           )
        addr1_pos = brute_compare.get('addr1_pos')
        addr2_pos = brute_compare.get('addr2_pos')
        if addr1_pos is not None and addr2_pos is not None:
            cleaned_addr1 = self._rebuild_addresses(addr1_pos, cleaned_addr1)
            cleaned_addr2 = self._rebuild_addresses(addr2_pos, cleaned_addr2)

        # assumption_search expect province to be the last part
        mapped_addr = self.extractor.assumption_search(cleaned_addr1)
        mapped_compare = self.extractor.assumption_search(cleaned_addr2)

        full_string_result = full_string_compare(cleaned_addr1, cleaned_addr2)
        type = mapped_addr.get('type', '') + '_' + mapped_compare.get('type', '')
        final_result = self._write_compare_result(type=type, mapped_addr=mapped_addr,
                                                  mapped_compare=mapped_compare,
                                                  full_string_result=full_string_result, group_result=brute_compare
                                                  )

        return final_result

    def _compare_with_assumption_brute_force_search(self, cleaned_addr1, cleaned_addr2, key_value_pairs1,
                                                    key_value_pairs2):
        no_of_groups_addr1 = len(key_value_pairs1.keys())
        no_of_groups_addr2 = len(key_value_pairs2.keys())

        brute_compare = self.brute_compare(cleaned_addr1, cleaned_addr2, is_cleaned=True,
                                           no_part_of_addr=no_of_groups_addr1,
                                           no_part_of_compare_addr=no_of_groups_addr2
                                           )
        addr1_pos = brute_compare.get('addr1_pos')
        addr2_pos = brute_compare.get('addr2_pos')
        cleaned_addr1 = brute_compare['cleaned_addr1']
        cleaned_addr2 = brute_compare['cleaned_addr2']
        if addr1_pos is not None and addr2_pos is not None:
            # Extract with addr1_pos/addr2_pos and rebuild with standard order street,ward,district,province
            cleaned_addr1 = self._rebuild_addresses(addr1_pos, cleaned_addr1)
            cleaned_addr2 = self._rebuild_addresses(addr2_pos, cleaned_addr2)

        mapped_addr = self.extractor.assumption_brute_force_search(cleaned_addr1)
        mapped_compare = self.extractor.assumption_brute_force_search(cleaned_addr2)

        full_string_result = full_string_compare(cleaned_addr1, cleaned_addr2)
        type = mapped_addr.get('type', '') + '_' + mapped_compare.get('type', '')
        final_result = self._write_compare_result(type=type, mapped_addr=mapped_addr,
                                                  mapped_compare=mapped_compare,
                                                  full_string_result=full_string_result, group_result=brute_compare
                                                  )
        return final_result

    def fuzzy_compare(self, addr: str, compare_addr: str):

        # Decide how many part/group of the address: expected a dict with 0->4 groups
        key_value_pairs1 = utils.extract_group(addr, self.group_keys)
        key_value_pairs2 = utils.extract_group(compare_addr, self.group_keys)

        no_of_groups_addr1 = len(key_value_pairs1.keys())
        no_of_groups_addr2 = len(key_value_pairs2.keys())

        # Do simple cleaning
        cleaned_addr1 = utils.clean_alphanumeric_delimeter_upper(addr)
        cleaned_addr2 = utils.clean_alphanumeric_delimeter_upper(compare_addr)

        # if no_of_groups_addr1 == 4 and no_of_groups_addr2 == 4:
        #     # 1st: find the best permutation of the 2 addresses, with highest match rate
        #     # 2nd: do brute force search to mapped thoses address to standardized domain
        #     # 3rd: try some comparison after mapping
        #     return self._compare_with_assumption_brute_force_search(cleaned_addr1, cleaned_addr2)
        # elif no_of_groups_addr1 == 0 or no_of_groups_addr2 == 0:
        #     return None
        # else:
        #     # In this case, those 2 addresses should not be aligned: do comparison as the whole string
        #     return self._compare_with_assumption_search(cleaned_addr1, cleaned_addr2)

        # if no_of_groups_addr1 == 0 or no_of_groups_addr2 == 0:
        #     return None
        # elif no_of_groups_addr1 == 1 or no_of_groups_addr2 == 1:
        #     return self._compare_with_assumption_search(cleaned_addr1, cleaned_addr2)
        # else:
        #     return self._compare_with_assumption_brute_force_search(cleaned_addr1, cleaned_addr2)

        # if no_of_groups_addr1 == 0 or no_of_groups_addr2 == 0:
        #     return None
        # elif no_of_groups_addr1 == 1 or no_of_groups_addr2 == 1:
        #     return self._compare_with_assumption_search_sorted(cleaned_addr1, cleaned_addr2,
        #                                                        key_value_pairs1=key_value_pairs1,
        #                                                        key_value_pairs2=key_value_pairs2,
        #                                                        )
        # else:
        #     return self._compare_with_assumption_brute_force_search(cleaned_addr1, cleaned_addr2)

        if no_of_groups_addr1 == 0 or no_of_groups_addr2 == 0:
            return None
        else:
            return self._compare_with_assumption_brute_force_search(cleaned_addr1, cleaned_addr2,
                                                                    key_value_pairs1=key_value_pairs1,
                                                                    key_value_pairs2=key_value_pairs2
                                                                    )
