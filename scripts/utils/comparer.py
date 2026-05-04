import re
from sentence_transformers import SentenceTransformer

class Comparer:
    _shared_model = None

    def __init__(self, list_of_configs: list[list[str]]):
        self.list_of_configs = list_of_configs

        if Comparer._shared_model is None:
            print("Loading SentenceTransformer model (first and only time)")
            Comparer._shared_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        self.model = Comparer._shared_model

        if not hasattr(Comparer, '_instance_count'):
            Comparer._instance_count = 0
        Comparer._instance_count += 1

        self.standard_threshold: float = 0.92
        self.english_threshold: float = 0.98
        self.dupes_to_delete_by_basename = self.get_dupes_by_base_name(self.list_of_configs)
        self.dupes_to_delete_by_model, self.manual_review = self.get_dupes_by_model(self.list_of_configs)

        self.all_dupes = self.dupes_to_delete_by_basename + self.dupes_to_delete_by_model
        
    def get_all_dupes(self):
        return self.all_dupes
    
    def get_dupes_to_be_reviewed(self) -> list[str]:
        return self.manual_review
    
    def model_compare(self, t1: str, t2: str) -> float:
        e1 = self.model.encode(t1)
        e2 = self.model.encode(t2)
        sim = self.model.similarity(e1, e2).item()
        return sim

    def has_parentheses(self, name: str) -> bool:
        return bool(re.search(r"\(.+\)", name))

    def get_dupes_by_base_name(self, config_list) -> list[list[str]]: 
        pattern = r'\s*\([^)]+\)\s*$'
        comics_by_base_name = {}
        dupes = []
        for sublist in self.list_of_configs:
            comic_name = sublist[0]
            base_name = re.sub(pattern, '', comic_name).strip()
            if base_name not in comics_by_base_name:
                comics_by_base_name[base_name] = []
            comics_by_base_name[base_name].append(sublist)

        for base_name, comics in comics_by_base_name.items():
            if len(comics) > 1:
                comic1, comic2 = comics
                name1 = comic1[0]
                name2 = comic2[0]
                check1 = self.has_parentheses(name1)
                check2 = self.has_parentheses(name2)
                if check1 and not check2:
                    dupes.append(comic2)
                elif check2 and not check1:
                    dupes.append(comic1)
        return dupes

    def get_dupes_by_model(self, config_list) -> list[list[str]]:
        similar_matches = []
        for idx in range(len(config_list) - 1):
            curr_list = config_list[idx]
            next_list = config_list[idx+1]
            curr_name = curr_list[0]
            next_name = next_list[0]
            similarity = self.model_compare(curr_name, next_name)
            if similarity > self.standard_threshold:
                similar_matches.append([curr_list, next_list])
        
        model_dupes = []
        manual_review = []
        for dupe_pair in similar_matches:
            sublist1, sublist2 = dupe_pair
            title1, domain1, *_ = sublist1
            title2, domain2, *_ = sublist2
            has_dash1 = '-' in title1
            has_dash2 = '-' in title2
            symbols = '?!.,:;'
            
            has_symbols1 = any(s in title1 for s in symbols)
            has_symbols2 = any(s in title2 for s in symbols)
            sim = self.model_compare(title1, title2)

            if has_dash1 and not has_dash2:
                model_dupes.append(sublist2)
            elif has_dash2 and not has_dash1:
                model_dupes.append(sublist1)
            elif has_symbols1 and not has_symbols2:
                model_dupes.append(sublist2)
            elif has_symbols2 and not has_symbols1:
                model_dupes.append(sublist1)
            elif sim > self.english_threshold:
                manual_review.append(dupe_pair)
            elif domain1 == 'hentai20':
                if 'high school' in title1.lower() and 'highschool' in title2.lower():
                    model_dupes.append(sublist2)
                elif 'high school' in title2.lower() and 'highschool' in title1.lower():
                    model_dupes.append(sublist1)
            else:
                manual_review.append(dupe_pair)

        return model_dupes, manual_review
