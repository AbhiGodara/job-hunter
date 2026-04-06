class EvaluationScorer:
    def __init__(self):
        self.dimensions = {
            'role_summary_match': 0,
            'cv_match_score_with_gaps_analysis': 0,
            'level_strategy_fit': 0,
            'compensation_research': 0,
            'personalization_potential': 0,
            'interview_prep_readiness': 0
        }
        self.weighted_average = 0.0

    def set_scores(self, scores):
        if len(scores) != len(self.dimensions):
            raise ValueError("Please provide exactly 6 scores.")
        for key in self.dimensions.keys():
            if key in scores:
                self.dimensions[key] = max(1, min(5, scores[key]))  # Ensure scores are between 1 and 5

    def calculate_weighted_average(self):
        self.weighted_average = sum(self.dimensions.values()) / len(self.dimensions)
        return self.get_grade()

    def get_grade(self):
        if self.weighted_average >= 4.5:
            return 'A'
        elif self.weighted_average >= 4.0:
            return 'B'
        elif self.weighted_average >= 3.0:
            return 'C'
        elif self.weighted_average >= 2.0:
            return 'D'
        else:
            return 'F'

if __name__ == '__main__':
    scorer = EvaluationScorer()
    example_scores = {
        'role_summary_match': 4,
        'cv_match_score_with_gaps_analysis': 3,
        'level_strategy_fit': 5,
        'compensation_research': 4,
        'personalization_potential': 2,
        'interview_prep_readiness': 4
    }
    scorer.set_scores(example_scores)
    final_grade = scorer.calculate_weighted_average()
    print(f'Final Grade: {final_grade}')  
