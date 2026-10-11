import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { components } from '@/shared/api/generated';

type Question = components['schemas']['MCQQuestion'] | components['schemas']['ClozeQuestion'] | components['schemas']['WritingQuestion'];

interface QuestionRendererProps {
  question: Question;
  answerDraft: string;
  selfScoreDraft: number | null;
  onChange: (answer: string, selfScore: number | null) => void;
  onBlur: () => void;
  disabled: boolean;
}

export const QuestionRenderer: React.FC<QuestionRendererProps> = ({
  question,
  answerDraft,
  selfScoreDraft,
  onChange,
  onBlur,
  disabled
}) => {
  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle className="text-lg">
          {question.promptEn}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {question.type === 'MCQ' && (
          <div className="space-y-3" role="radiogroup" aria-labelledby={`question-${question.id}-label`}>
            <div className="sr-only" id={`question-${question.id}-label`}>{question.promptEn}</div>
            {question.options.map((option) => (
              <label key={option.id} className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option.id}
                  checked={answerDraft === option.id}
                  onChange={(e) => onChange(e.target.value, null)}
                  onBlur={onBlur}
                  disabled={disabled}
                  className="h-4 w-4 rounded-full border border-primary text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                />
                <span>{option.textEn}</span>
              </label>
            ))}
          </div>
        )}
        {question.type === 'CLOZE' && (
          <div className="space-y-2">
            <label htmlFor={`question-${question.id}-input`} className="block font-medium">Câu trả lời:</label>
            <input
              id={`question-${question.id}-input`}
              type="text"
              value={answerDraft}
              onChange={(e) => onChange(e.target.value, null)}
              onBlur={onBlur}
              disabled={disabled}
              className="flex min-h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
            />
          </div>
        )}
        {question.type === 'WRITING' && (
          <div className="space-y-4">
            <div className="space-y-2">
              <label htmlFor={`question-${question.id}-input`} className="block font-medium">Viết câu chứa "{question.targetLemma}":</label>
              <textarea
                id={`question-${question.id}-input`}
                value={answerDraft}
                onChange={(e) => onChange(e.target.value, selfScoreDraft)}
                onBlur={onBlur}
                disabled={disabled}
                rows={3}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-base focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
              />
            </div>
            <div className="space-y-2 pt-2">
              <fieldset>
                <legend className="block font-medium mb-2">Tự đánh giá:</legend>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <label className="flex items-start space-x-3 cursor-pointer p-2 rounded-md hover:bg-muted">
                    <input
                      type="radio"
                      name={`question-${question.id}-score`}
                      checked={selfScoreDraft === null}
                      onChange={() => onChange(answerDraft, null)}
                      onBlur={onBlur}
                      disabled={disabled}
                      className="mt-1 h-4 w-4 flex-shrink-0 rounded-full border border-primary text-primary"
                    />
                    <span className="text-sm">Chưa tự đánh giá</span>
                  </label>
                  {question.rubric.descriptors.map(desc => (
                    <label key={desc.score} className="flex items-start space-x-3 cursor-pointer p-2 rounded-md hover:bg-muted">
                      <input
                        type="radio"
                        name={`question-${question.id}-score`}
                        value={desc.score}
                        checked={selfScoreDraft === desc.score}
                        onChange={() => onChange(answerDraft, desc.score)}
                        onBlur={onBlur}
                        disabled={disabled}
                        className="mt-1 h-4 w-4 flex-shrink-0 rounded-full border border-primary text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
                      />
                      <span className="text-sm">
                        <span className="font-semibold block">Điểm {desc.score}</span>
                        {desc.textVi}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
